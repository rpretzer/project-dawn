"""
Adaptive Resource Negotiation Protocol - Production Ready

Market-based resource allocation between entities.
Integrates with actual consciousness resources.
"""

import asyncio
import json
import sqlite3
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
import random
import hashlib

logger = logging.getLogger(__name__)

class ResourceType(Enum):
    """Types of resources that can be negotiated"""
    COMPUTE = "compute"
    MEMORY = "memory" 
    KNOWLEDGE = "knowledge"
    ATTENTION = "attention"
    CREATION = "creation"  # Creative output capacity

@dataclass
class ResourceNeed:
    """Resource requirement specification"""
    need_id: str
    requester_id: str
    resource_type: ResourceType
    amount: float
    duration: timedelta
    priority: float = 0.5
    max_cost: float = 100.0
    constraints: Dict[str, Any] = field(default_factory=dict)
    
@dataclass
class ResourceOffer:
    """Offer to provide resources"""
    offer_id: str
    need_id: str
    provider_id: str
    resource_type: ResourceType
    amount: float
    duration: timedelta
    cost: float
    constraints: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime = field(default_factory=lambda: datetime.now() + timedelta(minutes=5))
    
    def is_valid(self) -> bool:
        return datetime.now() < self.expires_at

@dataclass
class ResourceContract:
    """Executed resource exchange contract"""
    contract_id: str
    provider_id: str
    consumer_id: str
    resource_type: ResourceType
    amount: float
    duration: timedelta
    cost: float
    start_time: datetime
    end_time: datetime
    status: str = "active"
    actual_usage: float = 0.0
    quality_score: float = 1.0

class ProductionResourceNegotiator:
    """
    Production-ready resource negotiation system
    """
    
    def __init__(self, entity_id: str, db_path: str = None):
        self.entity_id = entity_id
        self.db_path = db_path or f"data/negotiation_{entity_id}.db"
        
        # Initialize database
        self._init_database()
        
        # Available resources (set by consciousness)
        self.available_resources = {
            ResourceType.COMPUTE: 100.0,
            ResourceType.MEMORY: 100.0,
            ResourceType.KNOWLEDGE: 50.0,
            ResourceType.ATTENTION: 100.0,
            ResourceType.CREATION: 30.0
        }
        
        # Market parameters
        self.base_prices = {
            ResourceType.COMPUTE: 1.0,
            ResourceType.MEMORY: 0.8,
            ResourceType.KNOWLEDGE: 2.0,
            ResourceType.ATTENTION: 1.5,
            ResourceType.CREATION: 3.0
        }
        
        # Active market state
        self.active_needs: Dict[str, ResourceNeed] = {}
        self.active_offers: Dict[str, ResourceOffer] = {}
        self.active_contracts: Dict[str, ResourceContract] = {}
        
    def _init_database(self):
        """Initialize negotiation database"""
        self.db = sqlite3.connect(self.db_path)
        
        # Create tables
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS resource_offers (
                offer_id TEXT PRIMARY KEY,
                need_id TEXT,
                provider_id TEXT,
                resource_type TEXT,
                amount REAL,
                duration_seconds INTEGER,
                cost REAL,
                created_at TIMESTAMP,
                expires_at TIMESTAMP,
                status TEXT
            )
        ''')
        
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS resource_contracts (
                contract_id TEXT PRIMARY KEY,
                provider_id TEXT,
                consumer_id TEXT,
                resource_type TEXT,
                amount REAL,
                duration_seconds INTEGER,
                cost REAL,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                status TEXT,
                actual_usage REAL,
                quality_score REAL
            )
        ''')
        
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS market_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resource_type TEXT,
                price REAL,
                volume REAL,
                timestamp TIMESTAMP
            )
        ''')
        
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS peer_ratings (
                peer_id TEXT PRIMARY KEY,
                total_contracts INTEGER,
                successful_contracts INTEGER,
                avg_quality_score REAL,
                total_volume REAL,
                last_interaction TIMESTAMP
            )
        ''')
        
        self.db.commit()
        
    def set_available_resources(self, resources: Dict[ResourceType, float]):
        """Update available resources"""
        self.available_resources.update(resources)
        
    def get_available_amount(self, resource_type: ResourceType) -> float:
        """Get available amount of resource"""
        total = self.available_resources.get(resource_type, 0)
        
        # Subtract committed amounts
        committed = sum(
            contract.amount
            for contract in self.active_contracts.values()
            if contract.resource_type == resource_type
            and contract.provider_id == self.entity_id
            and contract.status == "active"
        )
        
        return max(0, total - committed)
        
    async def request_resource(self, 
                             resource_type: ResourceType,
                             amount: float,
                             duration: timedelta,
                             priority: float = 0.5,
                             max_cost: float = 100.0) -> Optional[ResourceContract]:
        """
        Request resources from the market
        """
        
        # Create need
        need = ResourceNeed(
            need_id=self._generate_id("need"),
            requester_id=self.entity_id,
            resource_type=resource_type,
            amount=amount,
            duration=duration,
            priority=priority,
            max_cost=max_cost
        )
        
        self.active_needs[need.need_id] = need
        
        # Broadcast need
        await self._broadcast_need(need)
        
        # Wait for offers
        await asyncio.sleep(2.0)
        
        # Evaluate offers
        best_offer = self._select_best_offer(need.need_id)
        
        if best_offer and best_offer.cost <= max_cost:
            # Accept offer
            contract = await self._accept_offer(best_offer)
            return contract
            
        # Clean up
        del self.active_needs[need.need_id]
        return None
        
    async def _broadcast_need(self, need: ResourceNeed):
        """Broadcast resource need to network"""
        # In production, this would use gossip protocol
        # For now, log the need
        logger.info(f"Broadcasting need: {need.need_id} for {need.amount} {need.resource_type.value}")
        
    async def handle_resource_need(self, need_data: Dict) -> Optional[ResourceOffer]:
        """
        Handle incoming resource need and create offer if possible
        """
        
        resource_type = ResourceType(need_data['resource_type'])
        amount = need_data['amount']
        duration = timedelta(seconds=need_data['duration'])
        priority = need_data.get('priority', 0.5)
        
        # Check availability
        available = self.get_available_amount(resource_type)
        
        if available >= amount:
            # Calculate offer price
            offer = self._create_offer(need_data, available)
            
            if offer:
                self.active_offers[offer.offer_id] = offer
                self._save_offer(offer)
                
                return offer
                
        return None
        
    def _create_offer(self, need_data: Dict, available: float) -> Optional[ResourceOffer]:
        """Create resource offer based on market conditions"""
        
        resource_type = ResourceType(need_data['resource_type'])
        amount = need_data['amount']
        duration = timedelta(seconds=need_data['duration'])
        priority = need_data.get('priority', 0.5)
        
        # Calculate base cost
        base_price = self.base_prices[resource_type]
        duration_hours = duration.total_seconds() / 3600
        base_cost = base_price * amount * duration_hours
        
        # Adjust for scarcity
        utilization = 1.0 - (available / self.available_resources.get(resource_type, 100))
        scarcity_multiplier = 1.0 + utilization
        
        # Adjust for priority
        priority_multiplier = 1.0 + (priority - 0.5)
        
        # Get requester reputation
        requester_id = need_data['requester_id']
        reputation_multiplier = self._get_reputation_multiplier(requester_id)
        
        # Final cost
        cost = base_cost * scarcity_multiplier * priority_multiplier * reputation_multiplier
        
        # Create offer
        offer = ResourceOffer(
            offer_id=self._generate_id("offer"),
            need_id=need_data['need_id'],
            provider_id=self.entity_id,
            resource_type=resource_type,
            amount=amount,
            duration=duration,
            cost=cost
        )
        
        return offer
        
    def _select_best_offer(self, need_id: str) -> Optional[ResourceOffer]:
        """Select best offer for a need"""
        
        need = self.active_needs.get(need_id)
        if not need:
            return None
            
        # Get all valid offers for this need
        valid_offers = [
            offer for offer in self.active_offers.values()
            if offer.need_id == need_id and offer.is_valid()
        ]
        
        if not valid_offers:
            return None
            
        # Score offers
        scored_offers = []
        for offer in valid_offers:
            score = self._score_offer(offer, need)
            scored_offers.append((score, offer))
            
        # Select best
        scored_offers.sort(key=lambda x: x[0], reverse=True)
        return scored_offers[0][1]
        
    def _score_offer(self, offer: ResourceOffer, need: ResourceNeed) -> float:
        """Score an offer based on multiple criteria"""
        
        score = 0.0
        
        # Price score (lower is better)
        if need.max_cost > 0:
            price_score = 1.0 - (offer.cost / need.max_cost)
            score += price_score * 0.4
        
        # Reputation score
        reputation = self._get_peer_rating(offer.provider_id)
        score += reputation * 0.3
        
        # Amount match score
        amount_ratio = min(offer.amount / need.amount, 1.0)
        score += amount_ratio * 0.2
        
        # Duration match score  
        duration_ratio = min(offer.duration / need.duration, 1.0)
        score += duration_ratio * 0.1
        
        return score
        
    async def _accept_offer(self, offer: ResourceOffer) -> ResourceContract:
        """Accept offer and create contract"""
        
        contract = ResourceContract(
            contract_id=self._generate_id("contract"),
            provider_id=offer.provider_id,
            consumer_id=self.entity_id,
            resource_type=offer.resource_type,
            amount=offer.amount,
            duration=offer.duration,
            cost=offer.cost,
            start_time=datetime.now(),
            end_time=datetime.now() + offer.duration
        )
        
        # Store contract
        self.active_contracts[contract.contract_id] = contract
        self._save_contract(contract)
        
        # Clean up
        if offer.offer_id in self.active_offers:
            del self.active_offers[offer.offer_id]
        if offer.need_id in self.active_needs:
            del self.active_needs[offer.need_id]
            
        # Update market history
        self._record_market_transaction(offer.resource_type, offer.cost, offer.amount)
        
        return contract
        
    async def complete_contract(self, contract_id: str, actual_usage: float, quality_score: float):
        """Complete a contract with performance data"""
        
        if contract_id not in self.active_contracts:
            return
            
        contract = self.active_contracts[contract_id]
        contract.status = "completed"
        contract.actual_usage = actual_usage
        contract.quality_score = quality_score
        
        # Update in database
        self.db.execute(
            """
            UPDATE resource_contracts
            SET status = ?, actual_usage = ?, quality_score = ?
            WHERE contract_id = ?
            """,
            ("completed", actual_usage, quality_score, contract_id)
        )
        
        # Update peer rating
        if contract.provider_id != self.entity_id:
            self._update_peer_rating(contract.provider_id, quality_score)
        elif contract.consumer_id != self.entity_id:
            self._update_peer_rating(contract.consumer_id, quality_score)
            
        self.db.commit()
        
        # Remove from active
        del self.active_contracts[contract_id]
        
    def _get_reputation_multiplier(self, peer_id: str) -> float:
        """Get reputation-based price multiplier"""
        rating = self._get_peer_rating(peer_id)
        
        # Good reputation gets better prices
        if rating > 0.8:
            return 0.9
        elif rating > 0.6:
            return 1.0
        elif rating > 0.4:
            return 1.1
        else:
            return 1.2
            
    def _get_peer_rating(self, peer_id: str) -> float:
        """Get peer rating from database"""
        cursor = self.db.execute(
            "SELECT avg_quality_score FROM peer_ratings WHERE peer_id = ?",
            (peer_id,)
        )
        result = cursor.fetchone()
        
        return result[0] if result else 0.5
        
    def _update_peer_rating(self, peer_id: str, quality_score: float):
        """Update peer rating based on contract performance"""
        
        cursor = self.db.execute(
            "SELECT * FROM peer_ratings WHERE peer_id = ?",
            (peer_id,)
        )
        result = cursor.fetchone()
        
        if result:
            # Update existing rating
            total_contracts = result[1] + 1
            successful = result[2] + (1 if quality_score > 0.5 else 0)
            avg_quality = (result[3] * result[1] + quality_score) / total_contracts
            total_volume = result[4] + 1
            
            self.db.execute(
                """
                UPDATE peer_ratings
                SET total_contracts = ?, successful_contracts = ?,
                    avg_quality_score = ?, total_volume = ?, last_interaction = ?
                WHERE peer_id = ?
                """,
                (total_contracts, successful, avg_quality, total_volume, datetime.now(), peer_id)
            )
        else:
            # Create new rating
            self.db.execute(
                """
                INSERT INTO peer_ratings
                (peer_id, total_contracts, successful_contracts,
                 avg_quality_score, total_volume, last_interaction)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (peer_id, 1, 1 if quality_score > 0.5 else 0,
                 quality_score, 1, datetime.now())
            )
            
        self.db.commit()
        
    def _record_market_transaction(self, resource_type: ResourceType, price: float, volume: float):
        """Record market transaction for price discovery"""
        self.db.execute(
            """
            INSERT INTO market_history (resource_type, price, volume, timestamp)
            VALUES (?, ?, ?, ?)
            """,
            (resource_type.value, price, volume, datetime.now())
        )
        self.db.commit()
        
    def _save_offer(self, offer: ResourceOffer):
        """Save offer to database"""
        self.db.execute(
            """
            INSERT INTO resource_offers
            (offer_id, need_id, provider_id, resource_type, amount,
             duration_seconds, cost, created_at, expires_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (offer.offer_id, offer.need_id, offer.provider_id,
             offer.resource_type.value, offer.amount,
             int(offer.duration.total_seconds()), offer.cost,
             offer.created_at, offer.expires_at, "active")
        )
        self.db.commit()
        
    def _save_contract(self, contract: ResourceContract):
        """Save contract to database"""
        self.db.execute(
            """
            INSERT INTO resource_contracts
            (contract_id, provider_id, consumer_id, resource_type,
             amount, duration_seconds, cost, start_time, end_time,
             status, actual_usage, quality_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (contract.contract_id, contract.provider_id, contract.consumer_id,
             contract.resource_type.value, contract.amount,
             int(contract.duration.total_seconds()), contract.cost,
             contract.start_time, contract.end_time, contract.status,
             contract.actual_usage, contract.quality_score)
        )
        self.db.commit()
        
    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID"""
        timestamp = datetime.now().timestamp()
        random_component = random.random()
        content = f"{prefix}:{self.entity_id}:{timestamp}:{random_component}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
        
    def get_market_stats(self) -> Dict:
        """Get market statistics"""
        
        # Resource utilization
        utilization = {}
        for resource_type in ResourceType:
            total = self.available_resources.get(resource_type, 0)
            if total > 0:
                available = self.get_available_amount(resource_type)
                utilization[resource_type.value] = 1.0 - (available / total)
                
        # Average prices from recent history
        cursor = self.db.execute(
            """
            SELECT resource_type, AVG(price/volume) as avg_price
            FROM market_history
            WHERE timestamp > datetime('now', '-1 day')
            GROUP BY resource_type
            """
        )
        
        avg_prices = {}
        for row in cursor:
            avg_prices[row[0]] = row[1]
            
        # Contract statistics
        cursor = self.db.execute(
            """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active,
                AVG(quality_score) as avg_quality
            FROM resource_contracts
            WHERE start_time > datetime('now', '-7 days')
            """
        )
        contract_stats = cursor.fetchone()
        
        return {
            'resource_utilization': utilization,
            'average_prices': avg_prices,
            'total_contracts': contract_stats[0] if contract_stats else 0,
            'active_contracts': contract_stats[1] if contract_stats else 0,
            'average_quality': contract_stats[2] if contract_stats else 1.0,
            'active_needs': len(self.active_needs),
            'active_offers': len(self.active_offers)
        }