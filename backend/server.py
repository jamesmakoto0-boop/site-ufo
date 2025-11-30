from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# Define Models
class MenuItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    price: float
    category: str  # "burger", "dessert", "side", etc.
    tag: Optional[str] = None  # "Signature", "Hot", "Smash", "Sucré"
    image_url: Optional[str] = None
    is_available: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class MenuItemCreate(BaseModel):
    name: str
    description: str
    price: float
    category: str
    tag: Optional[str] = None
    image_url: Optional[str] = None
    is_available: bool = True

class MenuItemUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    category: Optional[str] = None
    tag: Optional[str] = None
    image_url: Optional[str] = None
    is_available: Optional[bool] = None


# Menu Routes
@api_router.get("/menu", response_model=List[MenuItem])
async def get_menu_items():
    """Get all menu items"""
    items = await db.menu_items.find({}, {"_id": 0}).to_list(1000)
    
    for item in items:
        if isinstance(item.get('created_at'), str):
            item['created_at'] = datetime.fromisoformat(item['created_at'])
    
    return items

@api_router.get("/menu/{item_id}", response_model=MenuItem)
async def get_menu_item(item_id: str):
    """Get a specific menu item"""
    item = await db.menu_items.find_one({"id": item_id}, {"_id": 0})
    
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    if isinstance(item.get('created_at'), str):
        item['created_at'] = datetime.fromisoformat(item['created_at'])
    
    return item

@api_router.post("/menu", response_model=MenuItem)
async def create_menu_item(item_input: MenuItemCreate):
    """Create a new menu item"""
    item_dict = item_input.model_dump()
    menu_item = MenuItem(**item_dict)
    
    doc = menu_item.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    
    await db.menu_items.insert_one(doc)
    return menu_item

@api_router.put("/menu/{item_id}", response_model=MenuItem)
async def update_menu_item(item_id: str, item_update: MenuItemUpdate):
    """Update a menu item"""
    existing_item = await db.menu_items.find_one({"id": item_id}, {"_id": 0})
    
    if not existing_item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    update_data = item_update.model_dump(exclude_unset=True)
    
    if update_data:
        await db.menu_items.update_one(
            {"id": item_id},
            {"$set": update_data}
        )
    
    updated_item = await db.menu_items.find_one({"id": item_id}, {"_id": 0})
    
    if isinstance(updated_item.get('created_at'), str):
        updated_item['created_at'] = datetime.fromisoformat(updated_item['created_at'])
    
    return updated_item

@api_router.delete("/menu/{item_id}")
async def delete_menu_item(item_id: str):
    """Delete a menu item"""
    result = await db.menu_items.delete_one({"id": item_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    
    return {"message": "Item deleted successfully"}

@api_router.post("/menu/seed")
async def seed_menu():
    """Seed initial menu data"""
    # Clear existing items
    await db.menu_items.delete_many({})
    
    initial_items = [
        {
            "id": str(uuid.uuid4()),
            "name": "Original Beef Bulgogi",
            "description": "Émincé de bœuf bulgogi, oignons rouges, poivrons, cheddar, salade, sauce secrète.",
            "price": 13.90,
            "category": "burger",
            "tag": "Signature",
            "image_url": "https://images.pexels.com/photos/5836779/pexels-photo-5836779.jpeg",
            "is_available": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Chicken Wasabi",
            "description": "Poulet frit à la coréenne, chou mariné, carottes, coriandre, cheddar, sauce mayo wasabi.",
            "price": 12.90,
            "category": "burger",
            "tag": "Hot",
            "image_url": "https://images.pexels.com/photos/4551304/pexels-photo-4551304.jpeg",
            "is_available": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Seoul Smash",
            "description": "Double steak smashé, cheddar, cornichons, oignons rouges, salade, sauce bulgogi.",
            "price": 13.90,
            "category": "burger",
            "tag": "Smash",
            "image_url": "https://images.pexels.com/photos/262897/pexels-photo-262897.jpeg",
            "is_available": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        },
        {
            "id": str(uuid.uuid4()),
            "name": "UFO Sucré",
            "description": "Base Glace ou Crème mousseline avec topping au choix (Oreo, Daim, M&M's...).",
            "price": 3.50,
            "category": "dessert",
            "tag": "Sucré",
            "image_url": "https://images.pexels.com/photos/2313686/pexels-photo-2313686.jpeg",
            "is_available": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
    ]
    
    await db.menu_items.insert_many(initial_items)
    
    return {"message": f"Seeded {len(initial_items)} menu items successfully"}

@api_router.get("/")
async def root():
    return {"message": "UFO B&N's API - Korean Fusion Street Food"}

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
