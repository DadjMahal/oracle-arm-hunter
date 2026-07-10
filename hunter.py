#!/usr/bin/env python3
# hunter.py - The main hunter logic: try to create an ARM instance 🎯
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
    """Main hunter that orchestrates the ARM instance provisioning."""

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

            # Start the endless hunting loop
            self._hunt_loop(ads, subnet.id, image.id)

        except KeyboardInterrupt:
            logger.warning("⏹️ Stopped by user.")
        except Exception as e:
            logger.error(f"💥 Fatal error: {str(e)}")
            debug(traceback.format_exc())
            telegram.notify_error(str(e), self.state)
            raise

    def _hunt_loop(self, ads, subnet_id, image_id):
        """Cycle through ADs until instance is created."""
        while True:
            self.state.next_cycle()
            cycle = self.state.data["cycle"]
            logger.info(f"\n{'='*60}")
            logger.info(f"🔄 Starting cycle #{cycle}")
            logger.info(f"{'='*60}")

            for ad in ads:
                self.state.set_ad(ad)
                self.state.next_attempt()
                attempt = self.state.data["attempt"]
                logger.info(f"🎯 Attempt #{attempt} | AD: {ad}")

                details = self.build_details(ad, subnet_id, image_id)
                try:
                    response = self.client.launch_instance(details)
                    instance_id = response.data.id
                    logger.success("🎉 INSTANCE CREATED!")
                    logger.success(f"🆔 ID: {instance_id}")

                    self.retry.success()

                    # Wait for public IP (up to 20 seconds)
                    ip = None
                    for _ in range(10):
                        ip = self.client.get_public_ip(instance_id)
                        if ip:
                            break
                        time.sleep(2)

                    self.state.success(instance_id, ip)
                    if ip:
                        logger.success(f"🌐 Public IP: {ip}")
                    else:
                        logger.warning("⚠️ No public IP assigned yet.")

                    logger.success("✅ Hunter finished successfully.")
                    telegram.notify_success(instance_id, ip, self.state)
                    return  # Exit program

                except ServiceError as e:
                    self._handle_service_error(e, ad)

            # All ADs tried, wait before next cycle
            delay = self.retry.wait_capacity()
            logger.info(f"⏳ All ADs exhausted. Waiting {delay}s before next cycle...")
            time.sleep(delay)

    def _handle_service_error(self, e, ad):
        """Process an OCI ServiceError with proper logging and retry logic."""
        if self.client.is_capacity_error(e):
            # Short warning to console, full details to debug log
            logger.warning(f"⚠️ {ad}: Out of host capacity")
            debug("Capacity error details:\n" + json.dumps({
                "ad": ad, "status": e.status, "code": e.code,
                "message": e.message, "request_id": getattr(e, 'request_id', 'N/A')
            }, indent=2))
            return  # continue to next AD

        if e.status == 429:
            delay = self.retry.wait_429()
            logger.warning(f"⏳ Rate limited (429). Sleeping {delay}s...")
            time.sleep(delay)
            return

        if e.status >= 500:
            delay = self.retry.wait_server_error()
            logger.warning(f"⚠️ Server error {e.status}. Sleeping {delay}s...")
            debug(f"Server error details: {e.message}")
            time.sleep(delay)
            return

        # Unknown critical error
        logger.error(f"💥 Unexpected OCI error: {e.message}")
        debug("Full error:\n" + json.dumps({
            "status": e.status, "code": e.code,
            "message": e.message, "request_id": getattr(e, 'request_id', 'N/A')
        }, indent=2))
        telegram.notify_error(f"Unexpected: {e.message}", self.state)
        raise

def main():
    """Entry point with process lock."""
    lock = ProcessLock()
    with lock:
        hunter = OracleArmHunter()
        hunter.run()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.warning("⏹️ Stopped by user.")
    except Exception as e:
        logger.error(f"💥 Fatal: {str(e)}")
        debug(traceback.format_exc())
    finally:
        # Ensure lock file is cleaned up
        if os.path.exists(config.LOCK_FILE):
            try:
                os.remove(config.LOCK_FILE)
            except Exception:
                pass
