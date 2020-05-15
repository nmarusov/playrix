import sys
from datetime import datetime, date
import getopt


DATE_FORMAT = '%Y-%m-%d'


def usage():
    """Справка по вызову скрипта."""
    print("""\
Анализ репозитория GitHub.

Использование:
python github_analyzer.py [опции] URL

Аргументы:
    URL    Ссылка на репозиторий GitHub.

Опции:
    -v, --verbose   Выводить дополнительные сообщения.
    -f, --from      Дата начала анализа в формате "ГГГГ-ММ-ДД". По умолчанию - без ограничения.
    -t, --to        Дата окончания анализа в формате "ГГГГ-ММ-ДД". По умолчанию - без ограничения.
    -b, --branch    Ветка репозитория. По умолчанию - master.
    -h, --help      Вывести это сообщение и вернуться.\
""")


def parse_args(input):
    """Разбор аргументов и опций командной строки."""
    opts, args = getopt.getopt(input, 'hf:t:b:v', [
        'help', 'url=', 'from=', 'to=', 'branch=', 'verbose'])
    url = None
    from_date = None
    to_date = date.today()
    verbose = False
    branch = 'master'

    if args:
        url = args[0]

    for o, a in opts:
        if o == '-v':
            verbose = True
        elif o in ('-h', '--help'):
            usage()
            sys.exit(0)
        elif o in ('-f', '--from'):
            from_date = datetime.strptime(a, DATE_FORMAT).date()
        elif o in ('-t', '--to'):
            to_date = datetime.strptime(a, DATE_FORMAT).date()
        elif o in ('-b', '--branch'):
            branch = a
        else:
            assert False, 'Как я сюда попал?'

    return url, from_date, to_date, verbose, branch


def main():
    """Точка входа."""
    try:
        url, from_date, to_date, verbose, branch = parse_args(sys.argv[1:])
    except getopt.GetoptError as err:
        print('Неизвестная опция: {}'.format(str(err)))
        usage()
        return 2

    if url is None:
        print('Не задан URL репозитория.')
        usage()
        return 2

    print(url, from_date, to_date, verbose, branch)

    return 0


if __name__ == '__main__':
    sys.exit(main())
