#!/usr/bin/env python3
# hunter.py - Fast cycles with smart adaptive micro-pacing 🎯
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
    """Main hunter that runs fast AD bursts with anti-burst micro-delays."""

    def __init__(self):
        self.state = State()
        self.retry = RetryManager()
        self.client = OracleClient()

        # Read SSH public key
        with open(config.SSH_KEY_PATH) as f:
            self.ssh_key = f.read().strip()

        logger.info("=" * 60)
        logger.info(f"🚀 Oracle ARM Hunter v{config.VERSION}")
        logger.info(f"🎯 Shape: {config.SHAPE} | OCPU: {config.OCPUS} | RAM: {config.MEMORY}GB")
        logger.info(f"🖥️  Instance name: {config.INSTANCE_NAME}")
        logger.info("=" * 60)

    def build_details(self, ad, subnet_id, image_id):
        """Construct launch details for the instance."""
        return oci.core.models.LaunchInstanceDetails(
            compartment_id=self.client.tenancy_id,
            availability_domain=ad,
            display_name=config.INSTANCE_NAME,
            shape=config.SHAPE,
            shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(
                ocpus=config.OCPUS,
                memory_in_gbs=config.MEMORY
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
            # 🤖 Fire up the interactive background command polling
            telegram.start_listener(self.state, self.retry)
            
            # Send standard boot alert
            telegram.notify_start(self.state)

            # Check if instance already running
            existing = self.client.instance_exists(config.INSTANCE_NAME)
            if existing:
                ip = self.client.get_public_ip(existing.id)
                self.state.success(existing.id, ip)
                logger.success(f"✔️ Instance already exists ({existing.id})")
                if ip:
                    logger.success(f"🌐 Public IP: {ip}")
                telegram.notify_success(existing.id, ip, self.state)
                return

            # Fetch needed resources
            image = self.client.get_latest_image()
            logger.info(f"🖼️  Using image: {image.display_name}")

            vcn = self.client.get_vcn()
            subnet = self.client.get_subnet(vcn.id)
            logger.info(f"🌐 Subnet: {subnet.id}")

            ads = self.client.get_availability_domains()
            logger.info(f"📍 Availability domains: {', '.join(ads)}")

            # Сюди передаємо саме image.id (Виправлено! 🛠️)
            self._hunt_loop(ads, subnet.id, image.id)

        except KeyboardInterrupt:
            logger.warning("⏹️ Stopped by user.")
        except Exception as e:
            logger.error(f"💥 Fatal error: {str(e)}")
            debug(traceback.format_exc())
            telegram.notify_error(str(e), self.state)
            raise

    def _hunt_loop(self, ads, subnet_id, image_id):
        """Fast burst loop through all ADs with dynamic anti-429 buffers between them."""
        while True:
            self.state.next_cycle()
            cycle = self.state.data["cycle"]
            logger.info(f"\n{'='*60}")
            logger.info(f"🔄 Starting cycle #{cycle}")
            logger.info(f"{'='*60}")

            for i, ad in enumerate(ads):
                self.state.set_ad(ad)
                self.state.next_attempt()
                attempt = self.state.data["attempt"]
                logger.info(f"🎯 Attempt #{attempt} | AD: {ad}")

                details = self.build_details(ad, subnet_id, image_id)
                is_capacity_limit = False
                
                try:
                    response = self.client.launch_instance(details)
                    instance_id = response.data.id
                    logger.success("🎉 INSTANCE CREATED!")
                    
                    self.retry.success()
                    ip = None
                    for _ in range(10):
                        ip = self.client.get_public_ip(instance_id)
                        if ip: break
                        time.sleep(2)

                    self.state.success(instance_id, ip)
                    telegram.notify_success(instance_id, ip, self.state)
                    return

                except ServiceError as e:
                    is_capacity_limit = self._handle_service_error(e, ad)

                # ⏱️ DYNAMIC MICRO-PACING (Driven by RetryManager optimization):
                if is_capacity_limit and i < len(ads) - 1:
                    m_delay = self.retry.get_micro_delay()
                    logger.info(f"⏱️  Micro-sleep {m_delay}s to evade Oracle Anti-DDoS filters...")
                    time.sleep(m_delay)

            # ⏳ Full cycle completed! Now we sleep the main adaptive time (25-35s)
            delay = self.retry.wait_capacity()
            logger.info(f"⏳ Cycle #{cycle} done. Waiting {delay}s before next full scan...")
            time.sleep(delay)

    def _handle_service_error(self, e, ad):
        """Process OCI ServiceError. Returns True if it was a capacity error."""
        if self.client.is_capacity_error(e):
            logger.warning(f"⚠️ {ad}: Out of host capacity")
            # Log metrics without triggering a long sleep inside the loop
            self.retry.data["last_error"] = "Out of host capacity"
            self.retry.data["total_retries"] += 1
            self.retry.data["retries_today"] += 1
            self.retry.save()
            return True

        if e.status == 429:
            delay = self.retry.wait_429()
            logger.warning(f"🛑 Rate limited (429)! Cooling down immediately for {delay}s...")
            time.sleep(delay)
            return False

        if e.status >= 500:
            delay = self.retry.wait_server_error()
            logger.warning(f"💥 Server error {e.status}. Sleeping {delay}s...")
            time.sleep(delay)
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
        sys.exit(1)
