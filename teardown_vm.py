"""VM停止・削除スクリプト。--action stop / delete で操作を分離する"""
import argparse
import time
import google.cloud.compute_v1 as compute_v1
from config import PROJECT, ZONE, VM_NAME


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


def stop_vm() -> None:
    instances_client = compute_v1.InstancesClient()
    ops_client = compute_v1.ZoneOperationsClient()

    vm = instances_client.get(project=PROJECT, zone=ZONE, instance=VM_NAME)
    if vm.status == "TERMINATED":
        print(f"VM {VM_NAME} is already stopped.")
        return

    print(f"Stopping VM {VM_NAME} ...")
    op = instances_client.stop(project=PROJECT, zone=ZONE, instance=VM_NAME)
    wait_for_operation(ops_client, op.name)
    print(f"VM {VM_NAME} stopped.")


def delete_vm(skip_confirm: bool = False) -> None:
    instances_client = compute_v1.InstancesClient()
    ops_client = compute_v1.ZoneOperationsClient()

    vm = instances_client.get(project=PROJECT, zone=ZONE, instance=VM_NAME)
    if vm.status not in ("TERMINATED", "STOPPED"):
        print(f"VM {VM_NAME} is {vm.status}. Stop it first before deleting.")
        print(f"  uv run python teardown_vm.py --action stop")
        raise SystemExit(1)

    if not skip_confirm:
        answer = input(f"Delete VM '{VM_NAME}' permanently? [yes/N]: ").strip().lower()
        if answer != "yes":
            print("Aborted.")
            return

    print(f"Deleting VM {VM_NAME} ...")
    op = instances_client.delete(project=PROJECT, zone=ZONE, instance=VM_NAME)
    wait_for_operation(ops_client, op.name)
    print(f"VM {VM_NAME} deleted.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--action",
        choices=["stop", "delete"],
        required=True,
        help="stop: stop the VM. delete: permanently delete the VM (must be stopped first).",
    )
    parser.add_argument("--yes", action="store_true", help="skip confirmation prompt")
    args = parser.parse_args()

    if args.action == "stop":
        stop_vm()
    else:
        delete_vm(skip_confirm=args.yes)


if __name__ == "__main__":
    main()
