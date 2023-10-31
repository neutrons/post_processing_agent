import datetime

ISO8601_fmt = "%Y-%m-%dT%H:%M"


def epochToISO8601(epoch):
    timestamp = datetime.datetime.fromtimestamp(epoch)
    return timestamp.strftime(ISO8601_fmt)
