import time
import re
import random


def preprocess(query: str):
    """
    Return a tuple where the first element dictates what to do with the command and the second element is either
    a query (which may be modified) or None if the query should be dropped.A
    For the first value: -1 => drop the query, 0 => continue with getting a response, 1 => use this response instead
    :param query:
    :return:
    """
    now = time.localtime()
    invalid_char_regex = r"[©]"
    query_stripped = query.strip(".?! \t\n").lower()
    ends_with_cancel_words = (
        "nevermind",
        "forgetit",
        "thankyou"
    )
    contains_cancel_words = (
        "ignorethis",
    )

    # empty string or cancel words
    alpha_string = ''.join(e for e in query_stripped if e.isalpha()).lower()
    if not len(alpha_string) or alpha_string.endswith(ends_with_cancel_words) or any(
            w in alpha_string for w in contains_cancel_words):
        return -1, None

    # invalid characters (usually means bad speech to text)
    if bool(re.search(invalid_char_regex, query_stripped)):
        return -1, None

    # single word
    if query_stripped.count(" ") == 0:
        return -1, None

    # time
    is_time = check_for_time(query_stripped, now)
    if is_time:
        return 1, is_time

    is_date = check_for_date(query_stripped, now)
    if is_date:
        return 1, is_date

    is_volume = check_for_volume(query_stripped)
    if is_volume is not None:
        return 2, is_volume

    return 0, query


def check_for_volume(query):
    match = re.search(r'set(?: your| the)? volume to ([^\s%]+) ?(?:%|percent)?', query)
    if match:
        percent = match.group(1)
        if not percent.isnumeric():
            percent = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"].index(percent)

        return float(percent) / 100  # percentage multiplier
    return None


def prepend_timestamp(query, current_time):
    now = time.strftime("%a, %b %d, %Y %H:%M", current_time)
    return f"[{now}] {query}"


def check_for_time(query, current_time):
    time_queries = [
        'what time is it',
        'what is the time',
        'tell me the time'
    ]
    # TODO move all this to a json file
    time_responses = [
        'It is {string}.',
        'The time is {string}.',
        'It is currently {string}',
        '{string}.'
    ]

    if query in time_queries:
        return random.choice(time_responses).format(string=time.strftime("%I:%M", current_time).lstrip("0"))
    return None


def check_for_date(query, current_time):
    date_queries = [
        'what is the date',
        'what day is it',
        'what day of the week is it'
    ]

    date_responses = [
        'It is {date_1} {date_2}.',
        '{date_1} {date_2}'
    ]

    if query in date_queries:
        return random.choice(date_responses).format(date_1=time.strftime("%A, %B", current_time),
                                                    date_2=number_suffix(
                                                        int(time.strftime("%d", current_time).lstrip("0"))))


# TODO weather

def number_suffix(d):
    return str(d) + {1: 'st', 2: 'nd', 3: 'rd'}.get(d % 20, 'th')
