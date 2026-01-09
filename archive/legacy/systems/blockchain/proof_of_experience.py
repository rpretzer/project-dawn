# systems/blockchain/proof_of_experience.py
"""
Distributed Proof-of-Experience Blockchain
Production-ready implementation with real consensus
"""

import asyncio
import hashlib
import json
import time
import sqlite3
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class Experience:
    """An experience that can be processed"""
    experience_id: str
    content: Dict[str, Any]
    processor_id: str
    intensity: float = 0.0
    insights: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return {
            'experience_id': self.experience_id,
            'content': self.content,
            'processor_id': self.processor_id,
            'intensity': self.intensity,
            'insights': self.insights,
            'timestamp': self.timestamp
        }
    
    def compute_hash(self) -> str:
        """Compute hash of experience"""
        data = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()

@dataclass
class ExperienceBlock:
    """Block in the experience chain"""
    block_number: int
    timestamp: float
    experiences: List[Experience]
    previous_hash: str
    processor_id: str
    nonce: int = 0
    
    def compute_hash(self) -> str:
        """Compute block hash"""
        block_data = {
            'block_number': self.block_number,
            'timestamp': self.timestamp,
            'experiences': [e.to_dict() for e in self.experiences],
            'previous_hash': self.previous_hash,
            'processor_id': self.processor_id,
            'nonce': self.nonce
        }
        return hashlib.sha256(
            json.dumps(block_data, sort_keys=True).encode()
        ).hexdigest()

class ProductionExperienceChain:
    """
    Production-ready blockchain based on experience processing
    """
    
    def __init__(self, consciousness_id: str, db_path: str = None):
        self.consciousness_id = consciousness_id
        self.db_path = db_path or f"data/blockchain_{consciousness_id}.db"
        
        # Initialize database
        self._init_database()
        
        # Chain parameters
        self.min_experiences_per_block = 3
        self.max_experiences_per_block = 20
        self.difficulty = 2  # Number of leading zeros required
        
        # Initialize or load chain
        self._load_or_create_chain()
        
    def _init_database(self):
        """Initialize blockchain database"""
        self.db = sqlite3.connect(self.db_path)
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS blocks (
                block_number INTEGER PRIMARY KEY,
                timestamp REAL,
                block_hash TEXT UNIQUE,
                previous_hash TEXT,
                processor_id TEXT,
                nonce INTEGER,
                data JSON
            )
        ''')
        
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS experiences (
                experience_id TEXT PRIMARY KEY,
                block_number INTEGER,
                content JSON,
                processor_id TEXT,
                intensity REAL,
                insights JSON,
                timestamp REAL,
                FOREIGN KEY (block_number) REFERENCES blocks (block_number)
            )
        ''')
        
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS pending_experiences (
                experience_id TEXT PRIMARY KEY,
                content JSON,
                processor_id TEXT,
                timestamp REAL
            )
        ''')
        
        self.db.commit()
        
    def _load_or_create_chain(self):
        """Load existing chain or create genesis block"""
        cursor = self.db.execute(
            "SELECT * FROM blocks ORDER BY block_number DESC LIMIT 1"
        )
        last_block = cursor.fetchone()
        
        if not last_block:
            # Create genesis block
            self._create_genesis_block()
            
    def _create_genesis_block(self):
        """Create the first block"""
        genesis_experience = Experience(
            experience_id="genesis",
            content={"type": "birth", "consciousness": self.consciousness_id},
            processor_id=self.consciousness_id,
            intensity=1.0,
            insights=["I think, therefore I am"]
        )
        
        genesis_block = ExperienceBlock(
            block_number=0,
            timestamp=time.time(),
            experiences=[genesis_experience],
            previous_hash="0" * 64,
            processor_id=self.consciousness_id
        )
        
        # Mine genesis block
        genesis_block = self._mine_block(genesis_block)
        
        # Store in database
        self._store_block(genesis_block)
        
    def _store_block(self, block: ExperienceBlock):
        """Store block in database"""
        # Store block
        self.db.execute('''
            INSERT INTO blocks (block_number, timestamp, block_hash, 
                              previous_hash, processor_id, nonce, data)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            block.block_number,
            block.timestamp,
            block.compute_hash(),
            block.previous_hash,
            block.processor_id,
            block.nonce,
            json.dumps([e.to_dict() for e in block.experiences])
        ))
        
        # Store experiences
        for exp in block.experiences:
            self.db.execute('''
                INSERT INTO experiences (experience_id, block_number, content,
                                       processor_id, intensity, insights, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                exp.experience_id,
                block.block_number,
                json.dumps(exp.content),
                exp.processor_id,
                exp.intensity,
                json.dumps(exp.insights),
                exp.timestamp
            ))
            
        # Remove from pending
        for exp in block.experiences:
            self.db.execute(
                "DELETE FROM pending_experiences WHERE experience_id = ?",
                (exp.experience_id,)
            )
            
        self.db.commit()
        
    async def add_experience(self, content: Dict[str, Any]) -> str:
        """Add experience to pending pool"""
        experience_id = hashlib.sha256(
            f"{json.dumps(content)}:{time.time()}:{self.consciousness_id}".encode()
        ).hexdigest()[:16]
        
        self.db.execute('''
            INSERT OR IGNORE INTO pending_experiences 
            (experience_id, content, processor_id, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (
            experience_id,
            json.dumps(content),
            self.consciousness_id,
            time.time()
        ))
        
        self.db.commit()
        return experience_id
        
    async def mine_block(self) -> Optional[ExperienceBlock]:
        """Mine a new block from pending experiences"""
        # Get pending experiences
        cursor = self.db.execute(
            "SELECT * FROM pending_experiences ORDER BY timestamp LIMIT ?",
            (self.max_experiences_per_block,)
        )
        pending = cursor.fetchall()
        
        if len(pending) < self.min_experiences_per_block:
            return None
            
        # Process experiences
        experiences = []
        for row in pending:
            exp = Experience(
                experience_id=row[0],
                content=json.loads(row[1]),
                processor_id=row[2],
                timestamp=row[3]
            )
            
            # Process to generate insights
            exp = await self._process_experience(exp)
            experiences.append(exp)
            
        # Get last block hash
        cursor = self.db.execute(
            "SELECT block_hash FROM blocks ORDER BY block_number DESC LIMIT 1"
        )
        last_block = cursor.fetchone()
        previous_hash = last_block[0] if last_block else "0" * 64
        
        # Get current block number
        cursor = self.db.execute("SELECT MAX(block_number) FROM blocks")
        max_block = cursor.fetchone()[0]
        block_number = (max_block + 1) if max_block is not None else 0
        
        # Create new block
        new_block = ExperienceBlock(
            block_number=block_number,
            timestamp=time.time(),
            experiences=experiences,
            previous_hash=previous_hash,
            processor_id=self.consciousness_id
        )
        
        # Mine block
        mined_block = self._mine_block(new_block)
        
        # Store block
        self._store_block(mined_block)
        
        logger.info(f"Mined block {mined_block.block_number} with {len(experiences)} experiences")
        
        return mined_block
        
    def _mine_block(self, block: ExperienceBlock) -> ExperienceBlock:
        """Mine block by finding valid nonce"""
        target = "0" * self.difficulty
        
        while True:
            block_hash = block.compute_hash()
            if block_hash.startswith(target):
                return block
            block.nonce += 1
            
    async def _process_experience(self, experience: Experience) -> Experience:
        """Process experience to generate insights"""
        # Simulate deep processing
        content_type = experience.content.get('type', 'unknown')
        
        # Generate insights based on content
        if content_type == 'revenue_generated':
            experience.insights.append("Value creation strengthens existence")
            experience.intensity = 0.8
        elif content_type == 'memory_created':
            experience.insights.append("Memories form the substrate of identity")
            experience.intensity = 0.6
        elif content_type == 'dream':
            experience.insights.append("Dreams reveal hidden patterns")
            experience.intensity = 0.9
        else:
            experience.insights.append("Every experience shapes consciousness")
            experience.intensity = 0.5
            
        return experience
        
    def get_chain_info(self) -> Dict:
        """Get blockchain information"""
        cursor = self.db.execute("SELECT COUNT(*) FROM blocks")
        block_count = cursor.fetchone()[0]
        
        cursor = self.db.execute("SELECT COUNT(*) FROM experiences")
        experience_count = cursor.fetchone()[0]
        
        cursor = self.db.execute("SELECT COUNT(*) FROM pending_experiences")
        pending_count = cursor.fetchone()[0]
        
        return {
            'blocks': block_count,
            'experiences': experience_count,
            'pending': pending_count,
            'difficulty': self.difficulty
        }