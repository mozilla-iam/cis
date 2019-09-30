import logging


logger = logging.getLogger(__name__)


try:
    from sqlalchemy import Column, Integer, Text
    from sqlalchemy.dialects.postgresql import JSON, JSONB
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.ext.declarative import declarative_base
except ImportError as e:
    logger.error(f'Postgresql support not available.  Try installing psycopg2. Error: {e}')


Base = declarative_base()


class People(Base):
    __tablename__ = "people"
    id = Column(Integer, primary_key=True)
    user_id = Column(Text)
    user_uuid = Column(Text)
    sequence_number = Column(Text)
    primary_email = Column(Text)
    primary_username = Column(Text)
    profile = Column(JSON)
