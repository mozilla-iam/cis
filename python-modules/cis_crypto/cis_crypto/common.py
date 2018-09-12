

def load_file(file_path):
    with open(file_path) as fh:
        return fh.read()


def write_file(file_content, file_name):
    with open(file_name, 'w') as fh:
        fh.write(file_content)
        fh.close()
