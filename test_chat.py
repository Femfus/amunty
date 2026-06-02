import asyncio
import json
import uuid
from amunty.models.odysseus_models import DATABASE_URL
from amunty.models.base import Base
from amunty.models.conversation import Conversation
from amunty.models.user import User
from amunty.services import chat_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from amunty.deps import get_db

async def test_chat():
    engine = create_async_engine(DATABASE_URL.replace("sqlite:", "sqlite+aiosqlite:"))
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        user_id = str(uuid.uuid4())
        conv_id = str(uuid.uuid4())
        # The user model in Amunty might not have email. Just use id and username if needed, or check model.
        user = User(id=user_id, password_hash="hash")
        conv = Conversation(id=conv_id, user_id=user_id, title="Test", model_id="gpt-3.5-turbo")
        db.add(user)
        db.add(conv)
        await db.commit()
        
        try:
            async for event in chat_engine.send_message(
                db=db,
                conversation_id=conv_id,
                user_id=user_id,
                content="Hello!",
                model_id="gpt-3.5-turbo"
            ):
                print("Event:", event)
        except Exception as e:
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_chat())
