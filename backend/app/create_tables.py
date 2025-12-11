# create_tables.py (backend 폴더에 하나 만들어두면 편함)
from app.db import Base, engine
from app import models  # noqa: F401


def main():
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    main()
