from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "mysql+pymysql://root:root@localhost/nopis"

# Add connection timeout and pool settings to prevent hanging
engine = create_engine(
    DATABASE_URL,
    connect_args={
        "connect_timeout": 10,
        "init_command": "SET SESSION MAX_EXECUTION_TIME=10000"
    },
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
