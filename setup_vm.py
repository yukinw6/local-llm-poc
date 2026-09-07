"""VM作成スクリプト: GCP GPU VM (T4) を作成して起動完了を待つ"""
import time
import google.cloud.compute_v1 as compute_v1
from config import (
    PROJECT, ZONE, VM_NAME, MACHINE_TYPE,
    GPU_TYPE, GPU_COUNT, DISK_SIZE_GB,
    IMAGE_PROJECT, IMAGE_FAMILY,
)


def get_latest_image(images_client: compute_v1.ImagesClient) -> str:
    image = images_client.get_from_family(project=IMAGE_PROJECT, family=IMAGE_FAMILY)
    print(f"Image: {image.name}")
    return image.self_link


def wait_for_operation(ops_client: compute_v1.ZoneOperationsClient, op_name: str) -> None:
    print(f"Waiting for operation {op_name} ...", end="", flush=True)
    while True:
        op = ops_client.get(project=PROJECT, zone=ZONE, operation=op_name)
        if op.status == compute_v1.Operation.Status.DONE:
            if op.error:
                raise RuntimeError(f"Operation failed: {op.error}")
            print(" done.")
            return
        print(".", end="", flush=True)
        time.sleep(5)


def create_vm() -> None:
    images_client = compute_v1.ImagesClient()
    instances_client = compute_v1.InstancesClient()
    ops_client = compute_v1.ZoneOperationsClient()

    image_link = get_latest_image(images_client)

    instance = compute_v1.Instance(
        name=VM_NAME,
        machine_type=f"zones/{ZONE}/machineTypes/{MACHINE_TYPE}",
        disks=[
            compute_v1.AttachedDisk(
                boot=True,
                auto_delete=True,
                initialize_params=compute_v1.AttachedDiskInitializeParams(
                    source_image=image_link,
                    disk_size_gb=DISK_SIZE_GB,
                    disk_type=f"zones/{ZONE}/diskTypes/pd-ssd",
                ),
            )
        ],
        guest_accelerators=[
            compute_v1.AcceleratorConfig(
                accelerator_type=f"zones/{ZONE}/acceleratorTypes/{GPU_TYPE}",
                accelerator_count=GPU_COUNT,
            )
        ],
        scheduling=compute_v1.Scheduling(
            on_host_maintenance="TERMINATE",
            automatic_restart=False,
            provisioning_model="SPOT",
        ),
        network_interfaces=[
            compute_v1.NetworkInterface(
                name="global/networks/default",
                access_configs=[
                    compute_v1.AccessConfig(
                        name="External NAT",
                        type_="ONE_TO_ONE_NAT",
                    )
                ],
            )
        ],
    )

    print(f"Creating VM {VM_NAME} in {ZONE} ...")
    op = instances_client.insert(project=PROJECT, zone=ZONE, instance_resource=instance)
    wait_for_operation(ops_client, op.name)

    vm = instances_client.get(project=PROJECT, zone=ZONE, instance=VM_NAME)
    print(f"VM status : {vm.status}")
    print(f"External IP: {vm.network_interfaces[0].access_configs[0].nat_i_p}")
    print()
    print("Next steps:")
    print(f"  gcloud compute scp install_ollama.sh {VM_NAME}:~ --zone={ZONE} --project={PROJECT}")
    print(f"  gcloud compute ssh {VM_NAME} --zone={ZONE} --project={PROJECT}")


if __name__ == "__main__":
    create_vm()
