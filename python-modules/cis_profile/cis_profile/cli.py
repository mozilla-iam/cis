import click
import json
import sys

from cis_profile.fake_profile import FakeUser, batch_create_fake_profiles, FakeProfileConfig

CONFIG_OPTIONS = [
    f for f in dir(FakeProfileConfig) if callable(getattr(FakeProfileConfig, f)) and not f.startswith("__")
]


@click.group()
def main():
    """cpf: CIS profile faker."""
    pass


@click.command()
@click.option("--seed", "-s", type=int, help="seed to create random profile", default=None)
@click.option(
    "--config",
    "-c",
    type=str,
    multiple=True,
    help="config options [{}]".format(", ".join(CONFIG_OPTIONS), default="default"),
)
def create(seed, config):
    """Create single IAM profile v2 object."""

    faker_config = FakeProfileConfig()
    for c in config:
        getattr(faker_config, c)()
    u = FakeUser(seed=seed, config=faker_config)
    click.echo(json.dumps(u.as_dict(), indent=2))


@click.command()
@click.option("--seed", "-s", type=int, help="seed to create random profile", default=1337)
@click.option("--number", "-n", type=int, help="how many profiles to create")
def batch(seed, number):
    """Create many IAM profile v2 objects."""
    profiles = batch_create_fake_profiles(seed, number)
    click.echo(json.dumps(profiles, indent=2))


main.add_command(create)
main.add_command(batch)

if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
