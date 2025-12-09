from dotenv import load_dotenv
import os
import psycopg2

from config import START_WORDS

load_dotenv()
HOST = os.environ.get('HOST')
PORT = os.environ.get('PORT')
DATABASE = os.environ.get('DATABASE')
DB_USER = os.environ.get('DB_USER')
DB_PASS = os.environ.get('DB_PASS')

# Проверяем все ли настройки БД есть в переменных окружения
if any(item is None for item in [HOST, PORT, DATABASE, DB_USER, DB_PASS]):
    raise ValueError('Параметры подключения к БД не установлены в переменных окружения.')

def create_db_connection():
    conn = psycopg2.connect(host=HOST, port=PORT, database=DATABASE, user=DB_USER, password=DB_PASS)
    return conn

def create_tables(conn):
    """
    Функция создает необходимые таблицы и наполняет БД стартовыми словами
    :param conn: объект connection
    :return: None
    """
    with conn.cursor() as cur:
        cur.execute("""
                CREATE TABLE IF NOT EXISTS users(
                    user_id BIGINT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL
                );
                """)

        cur.execute("""
                CREATE TABLE IF NOT EXISTS words(
                    word_id SERIAL PRIMARY KEY,
                    rus_word VARCHAR(100),
                    en_word VARCHAR(100),
                    CONSTRAINT ru_en UNIQUE (rus_word, en_word)
                );
                """)


        cur.execute("""
                CREATE TABLE IF NOT EXISTS userwords(
                    user_id BIGINT NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
                    word_id INT NOT NULL REFERENCES words (word_id) ON DELETE CASCADE,
                    wrong_answer INTEGER NOT NULL DEFAULT 0,
                    right_answer INTEGER NOT NULL DEFAULT 0,
                    CONSTRAINT user_word UNIQUE (user_id, word_id)
                );
                """)

        cur.executemany("""
                INSERT INTO words (word_id, rus_word, en_word)
                VALUES (%s, %s, %s)
                ON CONFLICT (word_id)
                DO NOTHING
                """, START_WORDS)

        cur.execute("""
                SELECT setval('words_word_id_seq', (SELECT MAX(word_id) FROM words))
                """)

        conn.commit()


def add_user(conn, user_id, user_name):
    """
    Функция добавляет пользователя в БД
    :param conn: объект connection
    :param user_id: номер пользователя в telegram
    :param user_name: имя пользователя для добавления
    :return: количество строк в результате выполнения функции
    """
    with conn.cursor() as cur:
        cur.execute("""
                INSERT INTO users (user_id, name)
                VALUES (%s, %s);
                """, (user_id, user_name))
        conn.commit()
        return cur.rowcount


def find_word(conn, word):
    """
    Функция ищет слово в таблице words
    :param conn: объект connection
    :param word: слово, которое необходимо найти
    :return: id искомого слова
    """
    word = word.lower()
    with conn.cursor() as cur:
        # Получаем id удаляемого слова
        cur.execute("""
                        SELECT word_id
                          FROM words
                         WHERE rus_word = %s OR en_word = %s
                         LIMIT 1;
                        """, (word, word))
        result = cur.fetchone()
        if result is not None:
            return result[0]

        return result

def add_words(conn, user_id, ru_word, en_word):
    """
    Функция сохраняет пару RU-EN слов в БД
    :param conn: объект connection
    :param user_id: номер пользователя в telegram
    :param ru_word: русское слово
    :param en_word: перевод русского слова
    :return: количество строк в результате выполнения функции
    """
    ru_word = ru_word.lower()
    en_word = en_word.lower()
    with conn.cursor() as cur:

        # Проверяем есть ли такая пара слов в нашей базе
        cur.execute("""
                SELECT word_id FROM words
                 WHERE rus_word = %s AND en_word = %s
                """, (ru_word, en_word))
        result = cur.fetchone()

        # Если такая пара есть в БД добавляем соответсвующую запись в таблицу userwords
        if result is not None:
            word_id = result[0]
            # Добавляем соответсвующую запись в таблицу userwords
            cur.execute("""
                    INSERT INTO userwords (user_id, word_id)
                    VALUES (%s, %s)
                    ON CONFLICT ON CONSTRAINT user_word
                    DO NOTHING
                    """, (user_id, word_id))
            conn.commit()
            return cur.rowcount
        # Если нет, добавляем и пару и запись в userwords
        else:
            cur.execute("""
                    WITH insert_word AS(
                        INSERT INTO words (rus_word, en_word)
                        VALUES (%s, %s)
                        ON CONFLICT ON CONSTRAINT ru_en
                        DO NOTHING
                        RETURNING word_id
                    )
                    INSERT INTO userwords (user_id, word_id)
                    VALUES (%s, (SELECT word_id FROM insert_word))
                    """, (ru_word, en_word, user_id))
            conn.commit()
            return cur.rowcount


def find_user(conn, user_id):
    """
    Функция ищет в БД пользователя по его id в telegram
    :param conn: объект connection
    :param user_id: номер пользователя в telegram
    :return: Имя пользователя если он есть в БД или None если его нет
    """
    with conn.cursor() as cur:
        cur.execute("""
                SELECT name
                  FROM users
                 WHERE user_id = %s
                """, (user_id,))
        return cur.fetchone()


def take_random_word(conn, user_id):
    """
    Функция выбирает из БД случайную пару EN-RU слов из 5 слов с худшими результатами по ответам
    :param conn: объект connection
    :param user_id: номер пользователя в telegram
    :return: кортеж с парой En-Ru слов
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT rus_word, en_word
              FROM (
                    SELECT w.rus_word, w.en_word
                      FROM words w
                      JOIN userwords uw
                        ON w.word_id = uw.word_id
                     WHERE uw.user_id = %s
                     ORDER BY ((uw.wrong_answer + 1.0) / (uw.right_answer + 1.0))
                     LIMIT 5
              ) as top
             ORDER BY RANDOM()
             LIMIT 1
                """, (user_id, ))
        result = cur.fetchone()

        # Если у пользователя нет ни одного слова в словаре выдаем слова из предустановленных
        if result is None:
            cur.execute("""
                SELECT rus_word, en_word
                  FROM (
                SELECT rus_word, en_word
                  FROM words
                 LIMIT 10
                ) as start_words
                 ORDER BY RANDOM()
                 LIMIT 1
                """)
            return cur.fetchone()
        return result


def take_other_words(conn, user_id, ex_word, lang, count=5):
    """
    Функция выбирает случайные слова, за исключением одного из БД
    для предложения их в качестве неправильных вариантов ответов
    :param conn: объект connection
    :param user_id: номер пользователя в telegram
    :param ex_word: слово, которое не должно попасть в выборку (правильный вариант ответа)
    :param lang: язык на котором должны быть слова
    :param count: количество возвращаемых слов
    :return: list из случайных слов
    """
    ex_word = ex_word.lower()
    with conn.cursor() as cur:
        if lang == 'ru':
            cur.execute("""
                    SELECT w.rus_word
                      FROM words w
                      JOIN userwords uw
                        ON w.word_id = uw.word_id
                     WHERE uw.user_id = %s AND w.rus_word <> %s
                     ORDER BY RANDOM() LIMIT %s
                    """, (user_id, ex_word, count))
            result = cur.fetchall()

            # Если слов в пользовательском словаре меньше чем нужно, берем слова из общего словаря
            if len(result) < count:
                limit = count - len(result)
                cur.execute("""
                        SELECT rus_word
                          FROM words
                         WHERE rus_word <> %s
                         LIMIT %s
                        """, (ex_word, limit, ))
                extra_words = cur.fetchall()
                result += extra_words

        else:
            cur.execute("""
                    SELECT w.en_word
                      FROM words w
                      JOIN userwords uw
                        ON w.word_id = uw.word_id
                     WHERE uw.user_id = %s AND w.en_word <> %s
                     ORDER BY RANDOM() LIMIT %s
                    """, (user_id, ex_word, count))
            result = cur.fetchall()
            if len(result) < count:
                limit = count - len(result)
                cur.execute("""
                        SELECT en_word
                          FROM words
                         WHERE en_word <> %s
                         LIMIT %s
                        """, (ex_word, limit, ))
                extra_words = cur.fetchall()
                result += extra_words
        return [x[0] for x in result]


def del_word(conn, user_id, word):
    """
    Функция удаляет слово из БД
    :param conn: объект connection
    :param user_id: номер пользователя в telegram
    :param word: слово, которое надо удалить
    :return: количество строк в результате выполнения функции
    """
    word = word.lower()
    with conn.cursor() as cur:
        # Получаем id удаляемого слова
        word_id = find_word(conn, word)
        if word_id is not None:
            cur.execute("""
                    DELETE FROM userwords
                     WHERE user_id = %s 
                       AND word_id = %s;
                    """, (user_id, word_id))
            conn.commit()
            return cur.rowcount
        else:
            return 0

def add_right_answer(conn, user_id, word):
    """
    Функция увеличивает на 1 счетчик правильных ответов для слова
    :param conn: объект connection
    :param user_id: номер пользователя в telegram
    :param word: слово для которого надо увеличить счетчик
    :return: None
    """
    word_id = find_word(conn, word)
    if word_id is not None:
        with conn.cursor() as cur:
            cur.execute("""
                    UPDATE userwords
                       SET right_answer = right_answer + 1
                     WHERE user_id = %s AND word_id = %s;
                    """, (user_id, word_id))
            conn.commit()


def add_wrong_answer(conn, user_id, word):
    """
    Функция увеличивает на 1 счетчик неправильных ответов для слова
    :param conn: объект connection
    :param user_id: номер пользователя в telegram
    :param word: слово для которого надо увеличить счетчик
    :return: None
    """
    word_id = find_word(conn, word)
    if word_id is not None:
        with conn.cursor() as cur:
            cur.execute("""
                    UPDATE userwords
                       SET wrong_answer = wrong_answer + 1
                     WHERE user_id = %s AND word_id = %s;
                    """, (user_id, word_id))
            conn.commit()

if __name__ == '__main__':
    conn = create_db_connection()
    print(find_word(conn, 'cat'))
    # print(add_words(conn, 525205107, 'дом2', 'house2'))
    conn.close()