import click
import json
import sys

from cis_profile.fake_profile import FakeUser, batch_create_fake_profiles


@click.group()
def main():
    """cpf: CIS profile faker."""
    pass


@click.command()
@click.option("--seed", type=int, help="seed to create random profile", default=None)
def create(seed):
    """Create single IAM profile v2 object."""

    u = FakeUser(seed=seed)
    click.echo(json.dumps(u.as_dict(), indent=2))


@click.command()
@click.option("--seed", type=int, help="seed to create random profile", default=1337)
@click.option("--count", type=int, help="how many profiles to create")
def batch(seed, count):
    """Create many IAM profile v2 objects."""
    profiles = batch_create_fake_profiles(seed, count)
    click.echo(json.dumps(profiles, indent=2))


main.add_command(create)
main.add_command(batch)

if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
