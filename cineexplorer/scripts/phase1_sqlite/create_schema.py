import sqlite3

def create_schema(db_path="cineexplorer/scripts/phase1_sqlite/cineexplorer.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()



    # Persons table:
    # pid (PK)
    # primaryName
    # birthYear
    # deathYear

    # PK: pid

    cursor.execute("DROP TABLE IF EXISTS Persons")
    cursor.execute("""
    CREATE TABLE Persons (
        pid TEXT PRIMARY KEY,
        primaryName TEXT,
        birthYear INTEGER,
        deathYear INTEGER
    )
    """)



    # Movies table:
    # mid (PK)
    # titleType
    # primaryTitle
    # originalTitle
    # isAdult
    # startYear
    # endYear
    # runtimeMinutes

    # PK: mid

    cursor.execute("DROP TABLE IF EXISTS Movies")
    cursor.execute("""
    CREATE TABLE Movies (
        mid TEXT PRIMARY KEY,
        titleType TEXT,
        primaryTitle TEXT,
        originalTitle TEXT,
        isAdult INTEGER,
        startYear INTEGER,
        endYear INTEGER,
        runtimeMinutes INTEGER
    )
    """)



    # Characters table:
    # mid (FID -> Movies.mid)
    # pid (FID -> Persons.pid
    # name
    # PK = (mid, pid, characterName)

    # PK: (mid, pid, characterName)
    # FK: mid, pid

    # diagramme Entité-Relation (ER):
    # [Movie] 1 ---- N [Characters] N ---- 1 [Persons]
    cursor.execute("DROP TABLE IF EXISTS Characters")
    cursor.execute("""
    CREATE TABLE Characters (
        mid TEXT,
        pid TEXT,
        characterName TEXT,
        PRIMARY KEY (mid, pid, characterName),
        FOREIGN KEY (mid) REFERENCES Movies(mid),
        FOREIGN KEY (pid) REFERENCES Persons(pid)
    )
    """)



    # Directors table:
    # mid (FID -> Movies.mid)
    # pid (FID -> Persons.pid)
    # PK = (mid, pid)

    # PK: (mid, pid)
    # FK: mid, pid

    # diagramme Entité-Relation (ER):
    # [Movie] 1 ---- N [Directors] N ---- 1 [Persons]
    cursor.execute("DROP TABLE IF EXISTS Directors")
    cursor.execute("""
    CREATE TABLE Directors (
        mid TEXT,
        pid TEXT,
        PRIMARY KEY (mid, pid),
        FOREIGN KEY (mid) REFERENCES Movies(mid),
        FOREIGN KEY (pid) REFERENCES Persons(pid)
    )
    """)



    # Genres table:
    # mid (FID -> Movies.mid)
    # genre
    # PK = (mid, genre)

    # PK: (mid, genre)
    # FK: mid

    # diagramme Entité-Relation (ER):
    # [Movie] 1 ---- N [Genres]
    cursor.execute("DROP TABLE IF EXISTS Genres")
    cursor.execute("""
    CREATE TABLE Genres (
        mid TEXT,
        genre TEXT,
        PRIMARY KEY (mid, genre),
        FOREIGN KEY (mid) REFERENCES Movies(mid)
    )
    """)



    # Knownformovies table:
    # mid (FID -> Movies.mid)
    # pid (FID -> Persons.pid)
    # PK = (mid, pid)

    # PK: (mid, pid)
    # FK: mid, pid

    # diagramme Entité-Relation (ER):
    # [Movie] 1 ---- N [Knownformovies] N ---- 1 [Persons]
    cursor.execute("DROP TABLE IF EXISTS KnownForMovies")
    cursor.execute("""
    CREATE TABLE KnownForMovies (
        mid TEXT,
        pid TEXT,
        PRIMARY KEY (mid, pid),
        FOREIGN KEY (mid) REFERENCES Movies(mid),
        FOREIGN KEY (pid) REFERENCES Persons(pid)
    )
    """)



    # Principals table:
    # mid (FID -> Movies.mid)
    # ordering
    # pid (FID -> Persons.pid)
    # category
    # job
    # PK = (mid, pid, ordering)

    # PK: (mid, pid, ordering)
    # FK: mid, pid

    # diagramme Entité-Relation (ER):
    # [Movie] 1 ---- N [Principals] N ---- 1 [Persons]
    cursor.execute("DROP TABLE IF EXISTS Principals")
    cursor.execute("""
    CREATE TABLE Principals (
        mid TEXT,
        pid TEXT,
        ordering INTEGER,
        category TEXT,
        job TEXT,
        PRIMARY KEY (mid, pid, ordering),
        FOREIGN KEY (mid) REFERENCES Movies(mid),
        FOREIGN KEY (pid) REFERENCES Persons(pid)
    )
    """)



    # Professions table:
    # pid (FID -> Persons.pid)
    # jobName
    # PK = (pid, jobName)

    # PK: (pid, jobName)
    # FK: pid

    # diagramme Entité-Relation (ER):
    # [Professions] N ---- 1 [Persons]
    cursor.execute("DROP TABLE IF EXISTS Professions")
    cursor.execute("""
    CREATE TABLE Professions (
        pid TEXT,
        jobName TEXT,
        PRIMARY KEY (pid, jobName),
        FOREIGN KEY (pid) REFERENCES Persons(pid)
    )
    """)



    # Ratings table:
    # mid (FID -> Movies.mid)
    # averageRating
    # numVotes
    # PK = (mid, averageRating)

    # PK: (mid, averageRating)
    # FK: mid

    # diagramme Entité-Relation (ER):
    # [Movie] 1 ---- 1 [Ratings]
    cursor.execute("DROP TABLE IF EXISTS Ratings")
    cursor.execute("""
    CREATE TABLE Ratings (
        mid TEXT PRIMARY KEY,
        averageRating REAL,
        numVotes INTEGER,
        FOREIGN KEY (mid) REFERENCES Movies(mid)
    )
    """)



    # Titles table:
    # mid (FID -> Movies.mid)
    # ordering
    # title
    # region
    # language
    # types
    # attributes
    # isOriginalTitle
    # PK = (mid, title)

    # PK: (mid, title)
    # FK: mid

    # diagramme Entité-Relation (ER):
    # [Movie] 1 ---- N [Titles]
    cursor.execute("DROP TABLE IF EXISTS Titles")
    cursor.execute("""
    CREATE TABLE Titles (
        mid TEXT,
        ordering INTEGER,
        title TEXT,
        region TEXT,
        language TEXT,
        types TEXT,
        attributes TEXT,
        isOriginalTitle INTEGER,
        PRIMARY KEY (mid, title),
        FOREIGN KEY (mid) REFERENCES Movies(mid)
    )
    """)



    # Writers table:
    # mid (FID -> Movies.mid)
    # pid (FID -> Persons.pid)
    # PK = (mid, pid)

    # PK: (mid, pid)
    # FK: mid, pid

    # diagramme Entité-Relation (ER):
    # [Movie] 1 ---- N [Writers] N ---- 1 [Persons]
    cursor.execute("DROP TABLE IF EXISTS Writers")
    cursor.execute("""
    CREATE TABLE Writers (
        mid TEXT,
        pid TEXT,
        PRIMARY KEY (mid, pid),
        FOREIGN KEY (mid) REFERENCES Movies(mid),
        FOREIGN KEY (pid) REFERENCES Persons(pid)
    )
    """)

    conn.commit()
    conn.close()
    print(f"Schema successfully created at {db_path}")


if __name__ == "__main__":
    create_schema()
