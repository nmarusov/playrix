import sys
from datetime import datetime, date
import getopt
import re
import requests


DATE_FORMAT = '%Y-%m-%d'
GITHUB_API_ROOT = 'https://api.github.com'
URL_PATTERN = re.compile(r'https://github.com/(?P<owner>\w+)/(?P<repo>\w+)')

ISSUES_TEMPLATE = \
    """
Issues
Открыто: {}     Закрыто: {}     Старые: {}"""


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
    -f, --from      Дата начала анализа в формате "ГГГГ-ММ-ДД".
                    По умолчанию - без ограничения.
    -t, --to        Дата окончания анализа в формате "ГГГГ-ММ-ДД"
                    (не включительно). По умолчанию - без ограничения.
    -b, --branch    Ветка репозитория. По умолчанию - master.
    -h, --help      Вывести это сообщение и вернуться.\
""")


def today():
    """Возвращает объект datetime с сегодняшней датой."""
    today = date.today()
    return datetime(today.year, today.month, today.day)


def parse_args(input):
    """Разбор аргументов и опций командной строки."""
    opts, args = getopt.getopt(input, 'hf:t:b:v', [
        'help', 'url=', 'from=', 'to=', 'branch=', 'verbose'])
    url = None
    from_date = None
    to_date = today()
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
            from_date = datetime.strptime(a, DATE_FORMAT)
        elif o in ('-t', '--to'):
            to_date = datetime.strptime(a, DATE_FORMAT)
        elif o in ('-b', '--branch'):
            branch = a
        else:
            assert False, 'Как я сюда попал?'

    return url, from_date, to_date, verbose, branch


def print_active_commiters(
        owner, repo, branch, from_date, to_date, max_commiters=30):
    """
    Самые активные участники.

    Таблица из 2 столбцов: login автора, количество его
    коммитов. Таблица отсортирована по количеству коммитов по убыванию. Не
    более 30 строк. Анализ производится на заданном периоде времени и заданной
    ветке.
    """
    pass


def print_pull_requests(owner, repo, branch, from_date, to_date):
    """
    Количество открытых и закрытых pull requests на заданном периоде времени по
    дате создания PR и заданной ветке, являющейся базовой для этого PR.
    """
    pass


def print_old_pull_requests(owner, repo, branch, from_date, to_date):
    """
    Количество "старых" pull requests на заданном периоде времени по дате
    создания PR и заданной ветке, являющейся базовой для этого PR.

    Pull request считается старым, если он не закрывается в течение 30 дней
    и до сих пор открыт.
    """
    pass


def count_issues(owner, repo, from_date, to_date, age=14):
    """Посчитывает количество issue с заданным состоянием."""
    def str2datetime(time_str):
        """Создаёт объект datetime из строки ISO-формата."""
        # Предварительно нужно удалить суффикс "Z", т.к. datetime
        # спотыкается на обработке таких строк
        return datetime.fromisoformat(time_str.replace('Z', ''))

    def count_open(response, to_date):
        """Подсчитывает количество открытых issue в ответе Github, фильтруя по
        дате окончания анализа."""
        return sum(1 for issue in response
                   if str2datetime(issue['created_at']) < to_date
                   and issue['state'] == 'open')

    def count_closed(response, to_date):
        """Подсчитывает количество открытых закрытых issue в ответе Github,
        фильтруя по дате окончания анализа."""
        return sum(1 for issue in response
                   if str2datetime(issue['created_at']) < to_date
                   and issue['state'] == 'closed')

    def count_state(response, to_date):
        """Подсчитывает количество закрытых issue в ответе Github, фильтруя по
        дате окончания анализа."""
        t = today()
        state_open = sum(1 for issue in response
                         if str2datetime(issue['created_at']) < to_date
                         and issue['state'] == 'open'
                         and (t - str2datetime(issue['created_at'])).days > age)
        # old_closed = sum(1 for issue in response
        # if issue['created_at'] < to_dat
        #  and issue['state'] == 'closed'
        # and (issue['closed_at'] - issue['created_at']).days > age)
        return state_open

    # Подготовить строку запроса а API
    url = f'{GITHUB_API_ROOT}/repos/{owner}/{repo}/issues'
    params = {'since': from_date.isoformat(), 'state': 'all'}

    total_open, total_closed, total_state = 0, 0, 0

    # Githib возвращает список issue постранично
    # Закончить, когда в ответе не будет ссылки на следующую страницу
    while True:
        r = requests.get(url, params=params)
        try:
            response = r.json()
            o, c, s = count_open(response, to_date), count_closed(
                response, to_date), count_state(response, to_date)
        except Exception as e:
            message = 'Не удалось подсчитать все issue '
            if rate_limit() == 0:
                message += 'т.к. исчерпан лимит запросов.'
            else:
                message += 'по причине "{}".'.format(
                    str(e))

            raise RuntimeError(message)

        # Аккумулируем полученные счётчики в итоговых счётчиках
        total_open += o
        total_closed += c
        total_state += s

        if 'next' not in r.links:
            break

        url = r.links['next']['url']
        break

    return total_open, total_closed, total_state


def print_issues(owner, repo, from_date, to_date):
    """
    Количество открытых и закрытых issues на заданном периоде времени.
    """
    report = ISSUES_TEMPLATE.format(
        *count_issues(owner, repo, from_date, to_date))
    print(report)


def parse_url(url):
    """Выделяет владельца и имя репоизитория из URL."""
    match = URL_PATTERN.search(url)
    owner = match['owner']
    repo = match['repo']

    return owner, repo


def rate_limit():
    """Возвращает количество оставшихся запросов в час."""
    url = f'{GITHUB_API_ROOT}/rate_limit'
    r = requests.get(url)
    return r.json()['rate']['remaining']


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

    try:
        owner, repo = parse_url(url)
    except KeyError:
        print('Неправильный формат строки URL ({}).'.format(url))
        return 2

    # 1
    # print_active_commiters(owner, repo, branch, from_date, to_date)
    # 2
    # print_pull_requests(owner, repo, branch, from_date, to_date)
    # 3
    # print_old_pull_requests(owner, repo, branch, from_date, to_date)
    # 4
    try:
        print_issues(owner, repo, from_date, to_date)
    except Exception as e:
        print('Не удалось сформировать отчёт по issue: {}', str(e))
        return -1

    return 0


if __name__ == '__main__':
    if rate_limit() == 0:
        print('Лимит запросов в час исчерпан.')
        sys.exit(-1)

    sys.exit(main())
