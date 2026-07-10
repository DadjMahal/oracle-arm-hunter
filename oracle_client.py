# oracle_client.py - Oracle Cloud API wrapper ☁️
import json
import oci
from oci.exceptions import ServiceError
import config
from logger import logger

class OracleClient:
    """
    Encapsulates all OCI SDK calls.
    Provides methods for AD listing, image search, instance management, etc.
    """
    def __init__(self):
        self.config = oci.config.from_file()
        self.identity = oci.identity.IdentityClient(self.config)
        self.compute = oci.core.ComputeClient(self.config)
        self.network = oci.core.VirtualNetworkClient(self.config)
        self.tenancy_id = self.config["tenancy"]

    def get_availability_domains(self):
        """Return a sorted list of availability domain names."""
        try:
            ads = self.identity.list_availability_domains(
                compartment_id=self.tenancy_id
            ).data
            ads.sort(key=lambda ad: ad.name)
            ad_names = [ad.name for ad in ads]
            logger.debug(f"📍 Found {len(ad_names)} ADs: {ad_names}")
            return ad_names
        except ServiceError as e:
            self._log_error("Failed to list ADs", e)
            raise

    def get_vcn(self):
        """Retrieve the first VCN in the compartment."""
        try:
            vcns = self.network.list_vcns(compartment_id=self.tenancy_id).data
            if not vcns:
                raise RuntimeError("❌ VCN not found.")
            return vcns[0]
        except ServiceError as e:
            self._log_error("Failed to list VCNs", e)
            raise

    def get_subnet(self, vcn_id):
        """Get the first subnet of a given VCN."""
        try:
            subnets = self.network.list_subnets(
                compartment_id=self.tenancy_id,
                vcn_id=vcn_id
            ).data
            if not subnets:
                raise RuntimeError("❌ Subnet not found.")
            return subnets[0]
        except ServiceError as e:
            self._log_error("Failed to list subnets", e)
            raise

    def instance_exists(self, name):
        """Check if an instance with the given display name already exists (non-terminated)."""
        try:
            instances = self.compute.list_instances(
                compartment_id=self.tenancy_id
            ).data
            for inst in instances:
                if inst.display_name == name and inst.lifecycle_state not in ("TERMINATED", "TERMINATING"):
                    logger.debug(f"✔️ Existing instance found: {inst.id}")
                    return inst
            return None
        except ServiceError as e:
            self._log_error("Failed to list instances", e)
            raise

    def get_latest_image(self):
        """Find the latest Ubuntu ARM image matching our criteria."""
        try:
            images = self.compute.list_images(
                compartment_id=self.tenancy_id,
                operating_system=config.IMAGE_OS
            ).data
            candidates = []
            for img in images:
                if config.IMAGE_VERSION in img.display_name and "aarch64" in img.display_name:
                    candidates.append(img)
            if not candidates:
                raise RuntimeError("❌ No suitable ARM image found.")
            candidates.sort(key=lambda x: x.time_created, reverse=True)
            image = candidates[0]
            logger.debug(f"🖼️ Selected image: {image.display_name} ({image.id})")
            return image
        except ServiceError as e:
            self._log_error("Failed to list images", e)
            raise

    def launch_instance(self, details):
        """Launch a new compute instance with given details."""
        return self.compute.launch_instance(details)

    def get_public_ip(self, instance_id):
        """Retrieve the public IP of an instance."""
        try:
            attachments = self.compute.list_vnic_attachments(
                compartment_id=self.tenancy_id,
                instance_id=instance_id
            ).data
            if not attachments:
                return None
            vnic = self.network.get_vnic(attachments[0].vnic_id).data
            return vnic.public_ip
        except ServiceError as e:
            self._log_error(f"Failed to get public IP for {instance_id}", e)
            raise

    def is_capacity_error(self, error):
        """
        Determine if an error is a capacity-related issue.
        Handles both 400/409 and 500 statuses with 'Out of host capacity' message.
        """
        if not isinstance(error, ServiceError):
            return False
        msg = str(error.message).lower() if error.message else ""
        if "out of host capacity" in msg:
            return True
        if "capacity" in msg and error.status in (400, 409, 500):
            return True
        return False

    def _log_error(self, context, error):
        """Log a short message to console and full JSON to debug log."""
        if isinstance(error, ServiceError):
            logger.error(f"❌ {context}: {error.message}")
            details = {
                "context": context,
                "status": error.status,
                "code": error.code,
                "message": error.message,
                "request_id": getattr(error, 'request_id', 'N/A')
            }
            logger.debug("OCI error details:\n" + json.dumps(details, indent=2))
        else:
            logger.error(f"❌ {context}: {str(error)}")
