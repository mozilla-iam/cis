import json
import os


class DisplayFakerPolicy:
    @staticmethod
    def max_display():
        def f(display):
            return display[0] if display else None

        return f

    @staticmethod
    def min_display():
        def f(display):
            return display[-1] if display else None

        return f

    @staticmethod
    def rand_display(random):
        def f(display):
            return random.choice(display) if display else None

        return f


class DisplayFaker(object):
    def __init__(self, schema="data/profile.schema"):
        self.schema = self.load_schema_from_file(schema)

    def display(self, field):
        return self._resolve(field.split("."))

    def load_schema_from_file(self, schema_json_path):
        if not os.path.isfile(schema_json_path):
            dirname = os.path.dirname(os.path.realpath(__file__))
            path = dirname + "/" + schema_json_path
        else:
            path = schema_json_path
        return json.load(open(path))

    def _resolve(self, field, level=None, display=None):
        if level is None:
            level = self._top_level()
        if "allOf" in level.keys():
            # We look for display rules and update display.
            definitions = list(map(extract_definition, level["allOf"]))
            rules = list(filter(is_display_definition, definitions))
            if rules:
                display = extract_display_levels(self._definition(rules[0]))
        if not field:
            return display
        head, tail = field[0], field[1:]
        if "properties" in level.keys():
            properties = level["properties"]
            if head in properties.keys():
                entry = properties[head]
                if "$ref" in entry.keys():
                    # We recurse into the definition.
                    return self._resolve(tail, self._definition(extract_definition(entry)), display)
                return self._resolve(tail, entry, display)
        return display

    def _top_level(self):
        return self._definition("Profile")

    def _definition(self, definition):
        return self.schema["definitions"][definition]

    def populate(self, profile_data, level=None, display=None, policy=DisplayFakerPolicy.min_display()):
        if level is None:
            level = self._top_level()
        if "allOf" in level.keys():
            # We look for display rules and update display.
            definitions = list(map(extract_definition, level["allOf"]))
            rules = list(filter(is_display_definition, definitions))
            if rules:
                display = extract_display_levels(self._definition(rules[0]))
        if "$ref" in level.keys():
            entry = extract_definition(level)
            self.populate(profile_data, self._definition(entry), display, policy)
        if hasattr(profile_data, "keys") and "metadata" in profile_data.keys():
            profile_data["metadata"]["display"] = policy(display)
        if "properties" in level.keys():
            properties = level["properties"]
            for k in properties.keys():
                if k in profile_data.keys():
                    self.populate(profile_data[k], properties[k], display, policy)


def extract_display_levels(definition):
    return definition["properties"]["metadata"]["properties"]["display"]["enum"]


# fmt: off
def extract_definition(definition):
    s = definition["$ref"]
    return s[s.rfind("/") + 1:]


def is_display_definition(s):
    return s.startswith("Display")
