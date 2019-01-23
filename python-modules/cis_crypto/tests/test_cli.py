class TestCli(object):
    def test_cli_object_init(self):
        from cis_crypto import cli

        c = cli.cli()
        assert c is not None

        res = c.parse_args(["sign", "--file", "foo"])
        assert res is not None
        res = c.parse_args(["verify", "--file", "foo.jws"])
