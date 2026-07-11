#!/usr/bin/env python3
# hunter.py - Multi-instance hunter with pause/resume/stop 🎯
import time
import sys
import traceback
import json
import os

import oci
from oci.exceptions import ServiceError

import config
from logger import logger, info, warning, error, success, debug
from state import State
from retry import RetryManager
from oracle_client import OracleClient
from telegram import notifier as telegram
from lock import ProcessLock

class OracleArmHunter:
    """Main hunter that can provision multiple ARM instances."""

    def __init__(self):
        self.state = State()
        self.retry = RetryManager()
        self.client = OracleClient()

        # Safe SSH key loading
        try:
            with open(config.SSH_KEY_PATH) as f:
                self.ssh_key = f.read().strip()
            if not self.ssh_key:
                raise ValueError(f"SSH key file is empty: {config.SSH_KEY_PATH}")
        except FileNotFoundError:
            logger.error(
                f"❌ SSH public key not found at {config.SSH_KEY_PATH}. "
                f"Run: mkdir -p ~/.ssh && echo '<your-public-key>' >> {config.SSH_KEY_PATH}"
            )
            sys.exit(1)
        except Exception as e:
            logger.error(f"❌ Failed to read SSH key: {e}")
            sys.exit(1)

        logger.info("=" * 60)
        logger.info(f"🚀 Oracle ARM Hunter v{config.VERSION}")
        logger.info(f"🎯 Shape: {config.SHAPE} | Max OCPU: {config.OCPUS} | Max RAM: {config.MEMORY}GB")
        logger.info(f"🖥️  Target instances: {len(config.INSTANCES)}")
        for inst in config.INSTANCES:
            logger.info(f"   • {inst['name']} ({inst['ocpus']} OCPU, {inst['memory']} GB)")
        logger.info("=" * 60)

    def build_details(self, ad, subnet_id, image_id, ocpus, memory):
        """Construct launch details for a specific instance size."""
        return oci.core.models.LaunchInstanceDetails(
            compartment_id=self.client.tenancy_id,
            availability_domain=ad,
            display_name=ad + "-" + str(int(time.time())),  # temporary, will rename after launch
            shape=config.SHAPE,
            shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(
                ocpus=ocpus,
                memory_in_gbs=memory
            ),
            source_details=oci.core.models.InstanceSourceViaImageDetails(
                source_type="image",
                image_id=image_id
            ),
            create_vnic_details=oci.core.models.CreateVnicDetails(
                subnet_id=subnet_id,
                assign_public_ip=True
            ),
            metadata={"ssh_authorized_keys": self.ssh_key}
        )

    def run(self):
        """Entry point for hunting process."""
        try:
            telegram.start_listener(self.state, self.retry)
            telegram.notify_start(self.state)

            # Check for already-existing instances
            all_exist = True
            for inst_cfg in config.INSTANCES:
                existing = self.client.instance_exists(inst_cfg["name"])
                if existing:
                    ip = self.client.get_public_ip(existing.id)
                    self.state.set_existing_instance(inst_cfg["name"], existing.id, ip)
                    logger.success(f"✔️ Instance '{inst_cfg['name']}' already exists ({existing.id})")
                    if ip:
                        logger.success(f"   🌐 Public IP: {ip}")
                    telegram.notify_success(existing.id, ip, self.state)
                else:
                    all_exist = False

            if all_exist:
                logger.success("✅ All target instances already exist. Nothing to do.")
                return

            # Fetch resources
            image = self.client.get_latest_image()
            logger.info(f"🖼️  Using image: {image.display_name}")
            vcn = self.client.get_vcn()
            subnet = self.client.get_subnet(vcn.id)
            logger.info(f"🌐 Subnet: {subnet.id}")
            ads = self.client.get_availability_domains()
            logger.info(f"📍 Availability domains: {', '.join(ads)}")

            self._hunt_loop(ads, subnet.id, image.id)

        except KeyboardInterrupt:
            logger.warning("⏹️ Stopped by user.")
        except Exception as e:
            logger.error(f"💥 Fatal error: {str(e)}")
            debug(traceback.format_exc())
            telegram.notify_error(str(e), self.state)
            raise

    def _hunt_loop(self, ads, subnet_id, image_id):
        """Main loop that cycles through ADs, trying to create pending instances one by one."""
        self.next_delay = None

        while True:
            # --- Check global stop/pause commands ---
            if self.state.data.get("stop_requested"):
                logger.info("🛑 Stop requested via Telegram. Shutting down gracefully.")
                telegram.send_message("🛑 Hunter stopped by user command.")
                return

            paused = self.state.data.get("paused", False)
            if paused:
                logger.info("⏸️  Hunter is paused. Waiting for /resume command...")
                time.sleep(5)
                continue

            # --- Determine next instance to work on ---
            pending = self.state.get_pending_instances()
            if not pending:
                logger.success("🎉 All instances have been created!")
                return

            # For safety, attempt only ONE instance per full AD cycle
            target = pending[0]

            self.state.next_cycle()
            cycle = self.state.data["cycle"]
            logger.info(f"\n{'='*60}")
            logger.info(f"🔄 Starting cycle #{cycle} — targeting '{target['name']}'")
            logger.info(f"{'='*60}")

            for i, ad in enumerate(ads):
                # Re-check pause/stop inside AD loop
                if self.state.data.get("stop_requested"):
                    logger.info("🛑 Stop requested during AD scan.")
                    return
                if self.state.data.get("paused"):
                    logger.info("⏸️  Paused during AD scan.")
                    break  # break out of AD loop, will sleep and resume later

                self.state.set_ad(ad)
                self.state.next_attempt()
                attempt = self.state.data["attempt"]
                logger.info(f"🎯 Attempt #{attempt} | AD: {ad} | Instance: {target['name']}")

                details = self.build_details(ad, subnet_id, image_id, target["ocpus"], target["memory"])
                is_capacity_limit = False

                try:
                    response = self.client.launch_instance(details)
                    instance_id = response.data.id
                    logger.success(f"🎉 INSTANCE '{target['name']}' CREATED!")

                    # Rename instance to match desired name
                    try:
                        self.client.compute.update_instance(
                            instance_id,
                            oci.core.models.UpdateInstanceDetails(display_name=target["name"])
                        )
                        logger.info(f"🏷️  Renamed instance to '{target['name']}'")
                    except Exception as rename_err:
                        logger.warning(f"⚠️ Could not rename instance: {rename_err}")

                    self.retry.success()

                    # Get public IP
                    ip = None
                    for _ in range(10):
                        ip = self.client.get_public_ip(instance_id)
                        if ip:
                            break
                        time.sleep(2)

                    self.state.mark_instance_success(target["name"], instance_id, ip)
                    if ip:
                        logger.success(f"🌐 Public IP: {ip}")
                    telegram.notify_success(instance_id, ip, self.state)

                    # Break out of AD loop to re-evaluate pending list
                    break

                except ServiceError as e:
                    is_capacity_limit = self._handle_service_error(e, ad)

                # Micro-delay between AD attempts (only after capacity errors)
                if is_capacity_limit and i < len(ads) - 1:
                    m_delay = self.retry.get_micro_delay()
                    logger.info(f"⏱️  Micro-sleep {m_delay}s to avoid rate limits...")
                    time.sleep(m_delay)

                # If a non-capacity error (429/5xx) occurred, break AD loop to apply delay
                if self.next_delay is not None:
                    break

            # End of AD loop
            if self.next_delay is not None:
                delay = self.next_delay
                self.next_delay = None
            else:
                delay = self.retry.wait_capacity()

            logger.info(f"⏳ Cycle #{cycle} done. Waiting {delay}s before next full scan...")
            time.sleep(delay)

    def _handle_service_error(self, e, ad):
        """
        Process OCI ServiceError.
        Returns True if it was a capacity error (continue AD loop),
        False for 429/5xx (break out of loop after setting self.next_delay).
        """
        if self.client.is_capacity_error(e):
            logger.warning(f"⚠️ {ad}: Out of host capacity")
            self.retry.data["last_error"] = "Out of host capacity"
            self.retry.data["total_retries"] += 1
            self.retry.data["retries_today"] += 1
            self.retry.save()
            return True

        if e.status == 429:
            delay = self.retry.wait_429()
            logger.warning(f"🛑 Rate limited (429)! Will wait {delay}s after this AD burst.")
            self.next_delay = delay
            return False

        if e.status >= 500:
            delay = self.retry.wait_server_error()
            logger.warning(f"💥 Server error {e.status}. Will wait {delay}s after this AD burst.")
            self.next_delay = delay
            return False

        logger.error(f"💥 Unexpected OCI error: {e.message}")
        telegram.notify_error(f"Unexpected: {e.message}", self.state)
        raise

if __name__ == "__main__":
    try:
        with ProcessLock():
            hunter = OracleArmHunter()
            hunter.run()
    except Exception as e:
        time.sleep(1)
        sys.exit(1)
