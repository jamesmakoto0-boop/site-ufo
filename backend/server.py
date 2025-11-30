from fastapi import FastAPI, APIRouter, HTTPException
# On garde dotenv seulement si le fichier existe (pour ton ordi), sinon on ignore (pour Render)
try:
    from dotenv import load_dotenv
    from pathlib import Path
    ROOT_DIR = Path(__file__).parent
    env_path = ROOT_DIR / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone
import uvicorn  # Il faudra peut-être ajouter 'uvicorn' à ton requirements.txt

# --- MongoDB connection ---
# Sur Render, si MONGO_URL n'est pas défini, ça plantera proprement
mongo_url = os.environ.get('MONGO_URL')
if not mongo_url:
    print("WARNING: MONGO_URL not found in environment variables!")
    # Valeur par défaut pour éviter le crash immédiat, mais ça ne marchera pas sans vraie URL
    mongo_url = "mongodb://localhost:27017"

client = AsyncIOMotorClient(mongo_url)
db_name = os.environ.get('DB_NAME', 'ufo_database') # Nom par défaut si non défini
db = client[db_name]

# --- Main App ---
app = FastAPI()
api_router = APIRouter(prefix="/api")

# --- Models (inchangés) ---
class MenuItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    price: float
    category: str 
    tag: Optional[str] = None
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

# --- Routes (inchangées) ---
@api_router.get("/menu", response_model=List[MenuItem])
async def get_menu_items():
    items = await db.menu_items.find({}, {"_id": 0}).to_list(1000)
    for item in items:
        if isinstance(item.get('created_at'), str):
            item['created_at'] = datetime.fromisoformat(item['created_at'])
    return items

@api_router.get("/menu/{item_id}", response_model=MenuItem)
async def get_menu_item(item_id: str):
    item = await db.menu_items.find_one({"id": item_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if isinstance(item.get('created_at'), str):
        item['created_at'] = datetime.fromisoformat(item['created_at'])
    return item

@api_router.post("/menu", response_model=MenuItem)
async def create_menu_item(item_input: MenuItemCreate):
    item_dict = item_input.model_dump()
    menu_item = MenuItem(**item_dict)
    doc = menu_item.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.menu_items.insert_one(doc)
    return menu_item

@api_router.put("/menu/{item_id}", response_model=MenuItem)
async def update_menu_item(item_id: str, item_update: MenuItemUpdate):
    existing_item = await db.menu_items.find_one({"id": item_id}, {"_id": 0})
    if not existing_item:
        raise HTTPException(status_code=404, detail="Item not found")
    update_data = item_update.model_dump(exclude_unset=True)
    if update_data:
        await db.menu_items.update_one({"id": item_id}, {"$set": update_data})
    updated_item = await db.menu_items.find_one({"id": item_id}, {"_id": 0})
    if isinstance(updated_item.get('created_at'), str):
        updated_item['created_at'] = datetime.fromisoformat(updated_item['created_at'])
    return updated_item

@api_router.delete("/menu/{item_id}")
async def delete_menu_item(item_id: str):
    result = await db.menu_items.delete_one({"id": item_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"message": "Item deleted successfully"}

@api_router.post("/menu/seed")
async def seed_menu():
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
        # ... (J'ai raccourci pour la lisibilité, tu peux garder ta liste complète) ...
    ]
    await db.menu_items.insert_many(initial_items)
    return {"message": f"Seeded menu items successfully"}

@api_router.get("/")
async def root():
    return {"message": "UFO B&N's API - Korean Fusion Street Food"}

app.include_router(api_router)

# --- CORS ---
# Important: Autoriser tout le monde en dev, ou spécifier le frontend en prod
origins = os.environ.get('CORS_ORIGINS', '*').split(',')
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Logging & Shutdown ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

# --- DEMARRAGE DU SERVEUR (TRES IMPORTANT POUR RENDER) ---
if __name__ == "__main__":
    # Render donne le port via la variable d'environnement PORT
    # Si elle n'existe pas (sur ton PC), on utilise 5000
    port = int(os.environ.get("PORT", 5000))
    
    # On lance uvicorn
    # host="0.0.0.0" est OBLIGATOIRE sur Render
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)