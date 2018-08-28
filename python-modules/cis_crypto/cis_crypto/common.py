

def load_file(file_path):
    fh = open(file_path)
    return fh.read()


def write_file(file_content, file_name):
    fh = open(file_name, 'w')
    fh.write(file_content)
    fh.close()
