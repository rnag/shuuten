from json import dumps
from logging import Formatter, LogRecord


class ShuutenJSONFormatter(Formatter):

    def format(self, record: LogRecord) -> str:
        # print(record.stack_info) # None
        base = {
            # 'ts': time(),
            'ts': record.created,
            'fn': record.funcName,
            'file': record.filename,
            'lineno': record.lineno,
            'level': record.levelname.lower(),
            'msg': record.getMessage(),
            'logger': record.name,
        }

        extra = getattr(record, 'shuuten', None)
        if extra:
            base['shuuten'] = extra
        if record.exc_info:
            base['exc'] = self.formatException(record.exc_info)

        return dumps(base, ensure_ascii=False)
