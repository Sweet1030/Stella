import asyncio
import aiosqlite
import os

DB_PATH = "stella.db"

async def add_column():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            # Check if column exists
            cursor = await db.execute("PRAGMA table_info(users)")
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            if "active_quest" in column_names:
                print("Column 'active_quest' already exists.")
            else:
                print("Adding 'active_quest' column to 'users' table...")
                await db.execute("ALTER TABLE users ADD COLUMN active_quest JSON")
                await db.commit()
                print("Column added successfully.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(add_column())
