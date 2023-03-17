import logging
import logging.config

DEFAULT_CONFIG = """
[loggers]
keys=root

[handlers]
keys=console,file

[formatters]
keys=simple,verbose

[formatter_simple]
format=%(message)s

[formatter_verbose]
format=%(asctime)s %(levelname)-8s [%(filename)s] %(message)s

[handler_console]
class=StreamHandler
level=DEBUG
formatter=simple
args=(sys.stdout,)

[handler_file]
class=FileHandler
level=INFO
formatter=verbose
args=('log.txt',)

[logger_root]
level=DEBUG
handlers=console,file
"""

def init_logging(log_config_path):
    print(f"Loading log configuration from {log_config_path}...")
    if not log_config_path.is_file():
        print("... doesn't exist, so create it.")
        with open(log_config_path, 'w') as fh:
            fh.write(DEFAULT_CONFIG)
    logging.config.fileConfig(log_config_path)
    return logging.getLogger('root')
