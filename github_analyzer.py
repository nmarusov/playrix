import sys
from datetime import datetime, date
import getopt


DATE_FORMAT = '%Y-%m-%d'
MAX_COMMITERS = 30


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


def print_active_commiters(max_commiters, branch, from_date, to_date):
    """
    Самые активные участники.

    Таблица из 2 столбцов: login автора, количество его
    коммитов. Таблица отсортирована по количеству коммитов по убыванию. Не
    более 30 строк. Анализ производится на заданном периоде времени и заданной
    ветке.
    """
    print(max_commiters, branch, from_date, to_date)


def print_pull_requests(branch, from_date, to_date):
    """
    Количество открытых и закрытых pull requests на заданном периоде времени по
    дате создания PR и заданной ветке, являющейся базовой для этого PR.
    """
    print(branch, from_date, to_date)


def print_old_pull_requests(branch, from_date, to_date):
    """
    Количество "старых" pull requests на заданном периоде времени по дате создания
    PR и заданной ветке, являющейся базовой для этого PR.

    Pull request считается старым, если он не закрывается в течение 30 дней и до сих пор открыт.
    """
    print(branch, from_date, to_date)


def print_issues(from_date, to_date):
    """
    Количество открытых и закрытых issues на заданном периоде времени по дате
    создания issue.
    """
    print(from_date, to_date)


def print_old_issues(from_date, to_date):
    """
    Количество “старых” issues на заданном периоде времени по дате создания issue.

    Issue считается старым, если он не закрывается в течение 14 дней.
    """
    print(from_date, to_date)


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

    # 1
    print_active_commiters(MAX_COMMITERS, branch, from_date, to_date)
    # 2
    print_pull_requests(branch, from_date, to_date)
    # 3
    print_old_pull_requests(branch, from_date, to_date)
    # 4
    print_issues(from_date, to_date)
    # 5
    print_old_issues(from_date, to_date)

    return 0


if __name__ == '__main__':
    sys.exit(main())
