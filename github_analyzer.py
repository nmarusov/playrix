import sys
from datetime import datetime, date
import getopt
import re
from collections import defaultdict
import requests


DATE_FORMAT = '%Y-%m-%d'
GITHUB_API_ROOT = 'https://api.github.com'
URL_PATTERN = re.compile(r'https://github.com/(?P<owner>\w+)/(?P<repo>\w+)')

ACTIVE_COMMITERS_TEMPLATE = \
    """
Логин автора         Кол-во коммитов
{}"""

PR_TEMPLATE = \
    """
Pull Requests
Открытых: {}     Закрытых: {}     Старых: {}"""

ISSUES_TEMPLATE = \
    """
Issues
Открытых: {}     Закрытых: {}     Старых: {}"""


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


# Вспомогательные функции

def today():
    """Возвращает объект datetime с сегодняшней датой."""
    today = date.today()
    return datetime(today.year, today.month, today.day)


def str2datetime(time_str):
    """Создаёт объект datetime из строки ISO-формата."""
    # Предварительно нужно удалить суффикс "Z", т.к. datetime
    # спотыкается на обработке таких строк
    return datetime.fromisoformat(time_str.replace('Z', ''))


def parse_url(url):
    """Выделяет владельца и имя репоизитория из URL."""
    match = URL_PATTERN.search(url)
    owner = match['owner']
    repo = match['repo']

    return owner, repo


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


def rate_limit():
    """Возвращает количество оставшихся запросов в час."""
    url = f'{GITHUB_API_ROOT}/rate_limit'
    r = requests.get(url)
    try:
        return r.json()['rate']['remaining']
    except Exception:
        print('Неправильный ответ сервера: {}'.format(r.text))
        sys.exit(-1)


def get_repository_start_date(owner, repo):
    """Получить дату создания репозитория."""
    url = f'{GITHUB_API_ROOT}/repos/{owner}/{repo}'
    r = requests.get(url)
    response = r.json()
    return str2datetime(response['created_at'])


# Функции анализа репозитория

def select_active_commiters(owner, repo, branch, from_date, to_date, limit=30):
    """
    Делает выборку самых активных участников разработки.
    """
    # Подготовить строку запроса а API
    url = f'{GITHUB_API_ROOT}/repos/{owner}/{repo}/commits'
    # Получить список коммитов в заданной ветке за заданный промежуток времени
    params = {
        'sha': branch,
        'since': from_date.isoformat(),
        'until': to_date.isoformat()
    }

    # Словарь участников в формате {login: count}
    commiters = defaultdict(int)

    # Githib возвращает список коммитов постранично
    # Закончить, когда в ответе не будет ссылки на следующую страницу
    while True:
        # Отправить запрос GitHub и получить ответ
        r = requests.get(url, params=params)

        # Бросить исключение, если код ответа не 200
        if r.status_code != 200:
            raise RuntimeError(
                'Сервер вернул код ошибки {}'.format(r.status_code))

        # Попробовать создать JSON-объект из ответа
        try:
            response = r.json()
        except Exception as e:
            message = 'Не удалось получить все коммиты '
            if rate_limit() == 0:
                message += 'т.к. исчерпан лимит запросов.'
            else:
                message += 'по причине "{}".'.format(
                    str(e))

            raise RuntimeError(message)

        # Некоторое количество коммитов должно быть, иначе прекратить
        # получать данные
        if not response or not isinstance(response, list):
            raise RuntimeError(
                'Неожиданный формат ответа: {}'.format(response))

        # Подсчитать количество коммитов от каждого участника
        try:
            for commit in response:
                commiters[commit['author']['login']] += 1
        except Exception as e:
            raise RuntimeError(
                'Не удалось получить логин участника: {}'.format(str(e)))

        # Это была последняя страница, больше нечего запрашивать
        if 'next' not in r.links:
            break

        url = r.links['next']['url']

    # Вернуть самых активных в виде списка кортежей [(login, count)],
    # ограничив количество TOP-участников
    return sorted(commiters.items(), key=lambda x: x[1], reverse=True)[:limit]


def count_pull_requests(owner, repo, branch, from_date, to_date, age=30):
    """
    Подсчитывает количества открытых, закрытых и "старых" PR.
    """
    def count_open(response):
        """Подсчитывает количество открытых PR на заданном интервале времени,
        фильтруя по дате создания."""
        return sum(1 for pr in response
                   # Окно даты создания
                   if str2datetime(pr['created_at']) < to_date
                   and str2datetime(pr['created_at']) >= from_date
                   # Открыт до сих пор или закрыт за пределами интревала
                   # анализа
                   and (pr['state'] == 'open'
                        or str2datetime(pr['closed_at']) >= to_date)
                   )

    def count_closed(response):
        """Подсчитывает количество закрытых PR на заданном интевале времени,
        фильтруя по дате создания."""
        return sum(1 for pr in response
                   # Окно даты создания
                   if str2datetime(pr['created_at']) < to_date
                   and str2datetime(pr['created_at']) >= from_date
                   # Закрыт до конца интервала анализа
                   and pr['state'] == 'closed'
                   and str2datetime(pr['closed_at']) < to_date)

    def count_stale(response):
        """Подсчитывает количество "старых" PR на заданном интевале времени,
        фильтруя по дате создания."""
        t = today()
        return sum(1 for pr in response
                   # Окно даты создания
                   if str2datetime(pr['created_at']) < to_date
                   and str2datetime(pr['created_at']) >= from_date
                   # Вариант, если "старость PR" понимается как "открыт до сих
                   # пор и более 30 дней"
                   and pr['state'] == 'open'
                   and (t - str2datetime(pr['created_at'])).days > age
                   # Вариант, если "старость PR" понимается именно на
                   # интервале анализа
                   #    and ((pr['state'] == 'open'
                   #          and to_date -
                   #          str2datetime(pr['created_at']).days > age)
                   #         or
                   #         (pr['state'] == 'closed'
                   #          and str2datetime(pr['closed_at']) -
                   #          str2datetime(pr['created_at']).days > age))
                   )

    # Подготовить строку запроса а API
    url = f'{GITHUB_API_ROOT}/repos/{owner}/{repo}/pulls'
    # Получить PRs всех состояний из нужной ветки
    # Выборка будет происходить постранично в порядке уменьшения
    # даты создания PR, начиная от сегодняшней даты
    params = {
        'base': branch,
        'state': 'all',
        'sort': 'created',
        'direction': 'desc'
    }

    # Инициализация счётчиков
    total_open, total_closed, total_state = 0, 0, 0

    # Githib возвращает список PR постранично
    # Закончить, когда в ответе не будет ссылки на следующую страницу
    while True:
        # Отправить запрос GitHub и получить ответ
        r = requests.get(url, params=params)

        # Бросить исключение, если код ответа не 200
        if r.status_code != 200:
            raise RuntimeError(
                'Сервер вернул код ошибки {}'.format(r.status_code))

        # Попробовать создать JSON-объект из ответа
        try:
            response = r.json()
        except Exception as e:
            message = 'Не удалось получить все PR '
            if rate_limit() == 0:
                message += 'т.к. исчерпан лимит запросов.'
            else:
                message += 'по причине "{}".'.format(
                    str(e))

            raise RuntimeError(message)

        # Некоторое количество PR должно быть, иначе прекратить
        # получать данные
        if not response or not isinstance(response, list):
            raise RuntimeError(
                'Неожиданный формат ответа: {}'.format(response))

        # Подсчитать количество открытых, закрытых и старых PR
        try:
            o, c, s = count_open(response), count_closed(
                response), count_stale(response)
        except Exception as e:
            raise RuntimeError(
                'Не удалось подсчитать все PR: {}'.format(str(e)))

        # Аккумулируем полученные счётчики в итоговых счётчиках
        total_open += o
        total_closed += c
        total_state += s

        # PR выдаются отсортированными в порядке убывания
        # даты их создания. Чтобы не делать лишних запросов, прекратить
        # получать страницы, когда дата создания последнего на странице
        # PR станет меньше даты начала анализа.
        if str2datetime(response[-1]['created_at']) < from_date:
            break

        # Это была последняя страница, больше нечего запрашивать
        if 'next' not in r.links:
            break

        url = r.links['next']['url']

    return total_open, total_closed, total_state


def count_issues(owner, repo, from_date, to_date, age=14):
    """Посчитывает количество issue."""

    def count_open(response,):
        """Подсчитывает количество открытых issue и не закрытых до конца
        интервала анализа, фильтруя по дате начала окончания анализа."""
        return sum(1 for issue in response
                   # Окно даты создания
                   if str2datetime(issue['created_at']) < to_date
                   and str2datetime(issue['created_at']) >= from_date
                   # Открыта до сих пор или не закрыта до конца интервала
                   # анализа
                   and (issue['state'] == 'open'
                        or str2datetime(issue['closed_at']) >= to_date)
                   )

    def count_closed(response):
        """Подсчитывает количество закрытых issue до конца интервала
        анализа, фильтруя по дате начала и окончания анализа."""
        return sum(1 for issue in response
                   # Окно даты создания
                   if str2datetime(issue['created_at']) < to_date
                   and str2datetime(issue['created_at']) >= from_date
                   # Закрыта до конца интервала анализа
                   and issue['state'] == 'closed'
                   and str2datetime(issue['closed_at']) < to_date)

    def count_stale(response):
        """Подсчитывает количество открытых issue возрастом более age дней,
        фильтруя по дате начала и окончания анализа."""
        t = today()
        return sum(1 for issue in response
                   # Окно даты создания
                   if str2datetime(issue['created_at']) < to_date
                   and str2datetime(issue['created_at']) >= from_date
                   # "Старость issue" понимается как "открыта до сих пор
                   # и более 14 дней"
                   and issue['state'] == 'open'
                   and (t - str2datetime(issue['created_at'])).days > age)

    # Подготовить строку запроса а API
    url = f'{GITHUB_API_ROOT}/repos/{owner}/{repo}/issues'
    # Получить список issue всех состояний с даты начала анализа,
    # отосортированный по убыванию даты создания issue
    params = {
        'state': 'all',
        'sort': 'created',
        'direction': 'desc'
    }

    # Инициализация счётчиков
    total_open, total_closed, total_state = 0, 0, 0

    # Githib возвращает список issue постранично
    # Закончить, когда в ответе не будет ссылки на следующую страницу
    while True:
        # Отправить запрос GitHub и получить ответ
        r = requests.get(url, params=params)

        # Бросить исключение, если код ответа не 200
        if r.status_code != 200:
            raise RuntimeError(
                'Сервер вернул код ошибки {}'.format(r.status_code))

        # Попробовать создать JSON-объект из ответа
        try:
            response = r.json()
        except Exception as e:
            message = 'Не удалось получить все issue '
            if rate_limit() == 0:
                message += 'т.к. исчерпан лимит запросов.'
            else:
                message += 'по причине "{}".'.format(
                    str(e))

            raise RuntimeError(message)

        # Некоторое количество issue должно быть, иначе прекратить
        # получать данные
        if not response or not isinstance(response, list):
            raise RuntimeError(
                'Неожиданный формат ответа: {}'.format(response))

        # Подсчитать количество открытых, закрытых и старых issue
        try:
            o, c, s = count_open(response), count_closed(
                response), count_stale(response)
        except Exception as e:
            raise RuntimeError(
                'Не удалось подсчитать все issue: {}'.format(str(e)))

        # Аккумулируем полученные счётчики в итоговых счётчиках
        total_open += o
        total_closed += c
        total_state += s

        # Issue выдаются отсортированными в порядке убывания
        # даты их создания. Чтобы не делать лишних запросов, прекратить
        # получать страницы, когда дата создания последней на странице
        # issue станет меньше даты начала анализа.
        if str2datetime(response[-1]['created_at']) < from_date:
            break

        # Это была последняя страница, больше нечего запрашивать
        if 'next' not in r.links:
            break

        url = r.links['next']['url']

    return total_open, total_closed, total_state


# Функции печати отчётов


def print_active_commiters(
        owner, repo, branch, from_date, to_date, max_commiters=30):
    """
    Самые активные участники.

    Таблица из 2 столбцов: login автора, количество его
    коммитов. Таблица отсортирована по количеству коммитов по убыванию. Не
    более 30 строк. Анализ производится на заданном периоде времени и заданной
    ветке.
    """
    commiters = select_active_commiters(
        owner, repo, branch, from_date, to_date, limit=max_commiters)
    report = ACTIVE_COMMITERS_TEMPLATE.format(
        '\n'.join('{:<20.20} {:6d}'.format(*item) for item in commiters)
    )
    print(report)


def print_pull_requests(owner, repo, branch, from_date, to_date, age=30):
    """
    Отчёт по PR.

    Количество открытых и закрытых pull requests на заданном периоде времени по
    дате создания PR и заданной ветке, являющейся базовой для этого PR.

    Количество "старых" pull requests на заданном периоде времени по дате
    создания PR и заданной ветке, являющейся базовой для этого PR.

    Pull request считается старым, если он не закрывается в течение 30 дней
    и до сих пор открыт.
    """
    report = PR_TEMPLATE.format(
        *count_pull_requests(owner, repo, branch, from_date, to_date, age=age))
    print(report)


def print_issues(owner, repo, from_date, to_date, age=14):
    """
    Отчёт по issues.

    Количество открытых и закрытых issues на заданном периоде времени.
    Количество "старых" issues на заданном периоде времени по дате создания
    issue. Issue считается старым, если он не закрывается в течение 14 дней.
    """
    report = ISSUES_TEMPLATE.format(
        *count_issues(owner, repo, from_date, to_date, age=age))
    print(report)


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

    # Попытаться разобрать переданный URL
    try:
        owner, repo = parse_url(url)
    except Exception:
        print('Неправильный формат строки URL ({}).'.format(url))
        return 2

    # Если дата начала анализа не указана, получить дату создания репозитория
    if from_date is None:
        try:
            from_date = get_repository_start_date(owner, repo)
        except Exception:
            print('Неожиданный ответ сервера')
            return -1

    if verbose:
        print('Анализ ветки {} репозитория {} с {} до {}'.format(
            branch, url, from_date.date(), to_date.date()))

    # Проверка исчерпания лимита запросов в GitHub
    limit = rate_limit()

    if limit == 0:
        print('Лимит запросов в час исчерпан.')
        sys.exit(-1)
    elif verbose:
        print('Оставший запас запросов: {}'.format(limit))

    # Отчёт по участникам
    if verbose:
        print('Получение данных для отчёта по самым активным участника.')

    try:
        print_active_commiters(owner, repo, branch, from_date, to_date)
    except Exception as e:
        print('Не удалось сформировать отчёт по участникам: {}'.format(str(e)))
        return -1

    # Отчёт по PR
    if verbose:
        print('Получение данных для отчёта по PR.')

    try:
        print_pull_requests(owner, repo, branch, from_date, to_date)
    except Exception as e:
        print('Не удалось сформировать отчёт по PR: {}'.format(str(e)))
        return -1

    # Отчёт по issue
    if verbose:
        print('Получение данных для отчёта по issue.')

    try:
        print_issues(owner, repo, from_date, to_date)
    except Exception as e:
        print('Не удалось сформировать отчёт по issue: {}'.format(str(e)))
        return -1

    if verbose:
        limit = rate_limit()
        print('Оставший запас запросов: {}'.format(limit))

    return 0


if __name__ == '__main__':
    sys.exit(main())
