"""Create pre-provisioned mobile pilot accounts without a public signup route."""

import argparse
from getpass import getpass

from cloud.db import init_cloud_db
from cloud.mobile_api import create_mobile_account


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision an FNK mobile pilot account")
    parser.add_argument("--username", required=True)
    parser.add_argument("--role", required=True, choices=("employee", "admin"))
    parser.add_argument("--employee-id", type=int, help="Required for employee accounts (FNK local employee ID)")
    parser.add_argument("--display-name")
    parser.add_argument("--department")
    parser.add_argument("--position")
    args = parser.parse_args()

    if args.role == "employee" and args.employee_id is None:
        parser.error("--employee-id is required for employee accounts")
    if args.role == "admin" and args.employee_id is not None:
        parser.error("--employee-id is only valid for employee accounts")

    password = getpass("Set mobile account password (10+ characters): ")
    confirmation = getpass("Confirm password: ")
    if password != confirmation:
        parser.error("Passwords did not match")

    init_cloud_db()
    account_id = create_mobile_account(
        username=args.username,
        password=password,
        role=args.role,
        local_user_id=args.employee_id,
        display_name=args.display_name,
        department=args.department,
        position=args.position,
    )
    print(f"Provisioned {args.role} account '{args.username}' ({account_id}).")


if __name__ == "__main__":
    main()