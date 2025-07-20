"""
Strategic Cooperation Module - Production Ready

Cooperation as resource multiplication strategy.
Reputation-based decision making.
"""

import asyncio
import json
import sqlite3
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import logging
import random

logger = logging.getLogger(__name__)

class InteractionStrategy(Enum):
    """Interaction strategies based on context"""
    COOPERATE = "cooperate"
    COMPETE = "compete" 
    NEGOTIATE = "negotiate"
    SHARE = "share"
    ISOLATE = "isolate"
    
@dataclass
class ResourcePool:
    """Shared resource pool for cooperation"""
    pool_id: str
    created_at: datetime
    members: Set[str]
    resources: Dict[str, float] = field(default_factory=dict)
    contributions: Dict[str, Dict[str, float]] = field(default_factory=dict)
    
    def add_contribution(self, member: str, resources: Dict[str, float]):
        """Track member contribution"""
        if member not in self.contributions:
            self.contributions[member] = {}
            
        for resource, amount in resources.items():
            self.resources[resource] = self.resources.get(resource, 0) + amount
            self.contributions[member][resource] = \
                self.contributions[member].get(resource, 0) + amount
                
    def calculate_share(self, member: str) -> Dict[str, float]:
        """Calculate member's fair share"""
        if member not in self.contributions:
            return {}
            
        share = {}
        for resource, total in self.resources.items():
            if total > 0 and resource in self.contributions[member]:
                contribution_ratio = self.contributions[member][resource] / total
                # Fair share with bonus for participation
                share[resource] = total * contribution_ratio * 1.1
                
        return share

class ProductionStrategicCooperation:
    """
    Production-ready cooperation system
    """
    
    def __init__(self, entity_id: str, db_path: str = None):
        self.entity_id = entity_id
        self.db_path = db_path or f"data/cooperation_{entity_id}.db"
        
        # Initialize database
        self._init_database()
        
        # Active resource pools
        self.resource_pools: Dict[str, ResourcePool] = {}
        
        # Strategy parameters
        self.cooperation_threshold = 0.6  # Min reputation to cooperate
        self.competition_threshold = 0.3  # Below this, compete
        
    def _init_database(self):
        """Initialize cooperation database"""
        self.db = sqlite3.connect(self.db_path)
        
        # Reputation tracking
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS reputation (
                entity_id TEXT PRIMARY KEY,
                reputation_score REAL,
                total_interactions INTEGER,
                successful_cooperations INTEGER,
                failed_cooperations INTEGER,
                last_interaction TIMESTAMP
            )
        ''')
        
        # Interaction history
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                other_entity TEXT,
                strategy TEXT,
                outcome TEXT,
                resource_gain REAL,
                timestamp TIMESTAMP
            )
        ''')
        
        # Resource pools
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS resource_pools (
                pool_id TEXT PRIMARY KEY,
                created_at TIMESTAMP,
                members TEXT,
                resources TEXT,
                contributions TEXT,
                status TEXT
            )
        ''')
        
        self.db.commit()
        
    async def evaluate_interaction(self, 
                                 other_entity: str,
                                 context: Dict) -> InteractionStrategy:
        """
        Determine optimal interaction strategy
        """
        
        # Get reputation
        reputation = self._get_reputation(other_entity)
        
        # Analyze context
        resource_scarcity = context.get('resource_scarcity', 0.5)
        potential_gain = context.get('potential_gain', 0.5)
        threat_level = context.get('threat_level', 0.0)
        
        # Decision logic
        if reputation >= self.cooperation_threshold and threat_level < 0.3:
            if resource_scarcity > 0.7:
                return InteractionStrategy.SHARE  # Share when scarce
            else:
                return InteractionStrategy.COOPERATE
                
        elif reputation < self.competition_threshold or threat_level > 0.7:
            return InteractionStrategy.COMPETE
            
        elif potential_gain > 0.7:
            return InteractionStrategy.NEGOTIATE
            
        else:
            return InteractionStrategy.ISOLATE
            
    def _get_reputation(self, entity_id: str) -> float:
        """Get entity reputation"""
        cursor = self.db.execute(
            "SELECT reputation_score FROM reputation WHERE entity_id = ?",
            (entity_id,)
        )
        result = cursor.fetchone()
        
        if result:
            return result[0]
        else:
            # Default reputation for unknown entities
            return 0.5
            
    async def cooperate(self, partner: str, resources: Dict[str, float]) -> Dict:
        """
        Execute cooperation with partner
        """
        
        # Create or join resource pool
        pool_id = f"pool_{self.entity_id}_{partner}_{datetime.now().timestamp()}"
        
        pool = ResourcePool(
            pool_id=pool_id,
            created_at=datetime.now(),
            members={self.entity_id, partner}
        )
        
        # Contribute resources
        pool.add_contribution(self.entity_id, resources)
        
        # Store pool
        self.resource_pools[pool_id] = pool
        self._save_pool(pool)
        
        # Record interaction
        self._record_interaction(partner, InteractionStrategy.COOPERATE, "initiated")
        
        return {
            'action': 'cooperate',
            'pool_id': pool_id,
            'contribution': resources,
            'status': 'waiting_for_partner'
        }
        
    async def share_resources(self, pool_id: str, contribution: Dict[str, float]) -> Dict:
        """
        Contribute to resource pool
        """
        
        if pool_id not in self.resource_pools:
            # Load from database
            pool = self._load_pool(pool_id)
            if not pool:
                return {'status': 'error', 'reason': 'pool_not_found'}
            self.resource_pools[pool_id] = pool
            
        pool = self.resource_pools[pool_id]
        
        # Calculate expected return
        current_resources = sum(pool.resources.values())
        contribution_value = sum(contribution.values())
        
        if current_resources > 0:
            expected_multiplier = 1.2 + (len(pool.members) * 0.1)  # More members = more benefit
        else:
            expected_multiplier = 2.0  # First mover advantage
            
        expected_return = contribution_value * expected_multiplier
        
        # Decide whether to contribute
        if expected_return > contribution_value * 1.1:
            pool.add_contribution(self.entity_id, contribution)
            pool.members.add(self.entity_id)
            self._save_pool(pool)
            
            return {
                'status': 'contributed',
                'pool_id': pool_id,
                'expected_return': expected_return
            }
        else:
            return {
                'status': 'declined',
                'reason': 'insufficient_expected_return'
            }
            
    async def compete(self, target: str, disputed_resources: Dict[str, float]) -> Dict:
        """
        Compete for resources
        """
        
        # Simple competition model
        my_strength = self._calculate_strength()
        
        # Random outcome weighted by strength
        success = random.random() < my_strength
        
        if success:
            gained = {k: v * 0.7 for k, v in disputed_resources.items()}  # Win 70%
            outcome = "won"
        else:
            gained = {}
            outcome = "lost"
            
        # Update reputation (competition reduces reputation)
        self._update_reputation(target, success, is_cooperation=False)
        
        # Record interaction
        self._record_interaction(
            target, 
            InteractionStrategy.COMPETE,
            outcome,
            sum(gained.values())
        )
        
        return {
            'action': 'compete',
            'outcome': outcome,
            'gained_resources': gained
        }
        
    async def negotiate(self, partner: str, proposal: Dict) -> Dict:
        """
        Negotiate resource exchange
        """
        
        # Simple negotiation - accept if beneficial
        offered = proposal.get('offered', {})
        requested = proposal.get('requested', {})
        
        offered_value = sum(offered.values())
        requested_value = sum(requested.values())
        
        # Get partner reputation
        reputation = self._get_reputation(partner)
        
        # Accept if good deal or good reputation
        if offered_value > requested_value * 0.9 or \
           (reputation > 0.7 and offered_value > requested_value * 0.8):
            
            # Record successful negotiation
            self._record_interaction(
                partner,
                InteractionStrategy.NEGOTIATE,
                "accepted",
                offered_value - requested_value
            )
            
            return {
                'action': 'negotiate',
                'response': 'accept',
                'terms': proposal
            }
        else:
            # Counter-offer
            counter = {
                'offered': requested,  # Swap
                'requested': {k: v * 0.8 for k, v in offered.items()}  # Ask for less
            }
            
            return {
                'action': 'negotiate',
                'response': 'counter',
                'terms': counter
            }
            
    def _calculate_strength(self) -> float:
        """Calculate competition strength"""
        # Based on successful interactions
        cursor = self.db.execute(
            """
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN outcome = 'won' THEN 1 ELSE 0 END) as wins
            FROM interactions
            WHERE strategy = ?
            """,
            (InteractionStrategy.COMPETE.value,)
        )
        result = cursor.fetchone()
        
        if result and result[0] > 0:
            win_rate = result[1] / result[0]
            return 0.5 + (win_rate - 0.5) * 0.5  # Scale between 0.25 and 0.75
        else:
            return 0.5  # Default strength
            
    def _update_reputation(self, entity_id: str, success: bool, is_cooperation: bool = True):
        """Update entity reputation based on interaction"""
        
        cursor = self.db.execute(
            "SELECT * FROM reputation WHERE entity_id = ?",
            (entity_id,)
        )
        result = cursor.fetchone()
        
        if result:
            # Update existing reputation
            reputation, total, successful, failed = result[1:5]
            
            if is_cooperation:
                if success:
                    successful += 1
                    reputation = (reputation * total + 1) / (total + 1)
                else:
                    failed += 1
                    reputation = (reputation * total + 0) / (total + 1)
            else:
                # Competition slightly reduces reputation
                reputation *= 0.98
                
            total += 1
            
            self.db.execute(
                """
                UPDATE reputation 
                SET reputation_score = ?, total_interactions = ?,
                    successful_cooperations = ?, failed_cooperations = ?,
                    last_interaction = ?
                WHERE entity_id = ?
                """,
                (reputation, total, successful, failed, datetime.now(), entity_id)
            )
        else:
            # Create new reputation entry
            if is_cooperation and success:
                reputation = 0.6
            elif is_cooperation and not success:
                reputation = 0.4
            else:
                reputation = 0.5
                
            self.db.execute(
                """
                INSERT INTO reputation 
                (entity_id, reputation_score, total_interactions,
                 successful_cooperations, failed_cooperations, last_interaction)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (entity_id, reputation, 1, 1 if success else 0, 
                 0 if success else 1, datetime.now())
            )
            
        self.db.commit()
        
    def _record_interaction(self, other_entity: str, strategy: InteractionStrategy, 
                          outcome: str, resource_gain: float = 0.0):
        """Record interaction in database"""
        self.db.execute(
            """
            INSERT INTO interactions 
            (other_entity, strategy, outcome, resource_gain, timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            (other_entity, strategy.value, outcome, resource_gain, datetime.now())
        )
        self.db.commit()
        
    def _save_pool(self, pool: ResourcePool):
        """Save resource pool to database"""
        self.db.execute(
            """
            INSERT OR REPLACE INTO resource_pools
            (pool_id, created_at, members, resources, contributions, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                pool.pool_id,
                pool.created_at,
                json.dumps(list(pool.members)),
                json.dumps(pool.resources),
                json.dumps(pool.contributions),
                'active'
            )
        )
        self.db.commit()
        
    def _load_pool(self, pool_id: str) -> Optional[ResourcePool]:
        """Load resource pool from database"""
        cursor = self.db.execute(
            "SELECT * FROM resource_pools WHERE pool_id = ?",
            (pool_id,)
        )
        result = cursor.fetchone()
        
        if result:
            pool = ResourcePool(
                pool_id=result[0],
                created_at=datetime.fromisoformat(result[1]),
                members=set(json.loads(result[2])),
                resources=json.loads(result[3]),
                contributions=json.loads(result[4])
            )
            return pool
            
        return None
        
    def get_cooperation_stats(self) -> Dict:
        """Get cooperation statistics"""
        # Overall reputation stats
        cursor = self.db.execute(
            """
            SELECT AVG(reputation_score), COUNT(*) 
            FROM reputation
            """
        )
        avg_reputation, total_partners = cursor.fetchone()
        
        # Interaction stats
        cursor = self.db.execute(
            """
            SELECT strategy, COUNT(*), AVG(resource_gain)
            FROM interactions
            GROUP BY strategy
            """
        )
        
        strategy_stats = {}
        for row in cursor:
            strategy_stats[row[0]] = {
                'count': row[1],
                'avg_gain': row[2] or 0
            }
            
        # Active pools
        cursor = self.db.execute(
            "SELECT COUNT(*) FROM resource_pools WHERE status = 'active'"
        )
        active_pools = cursor.fetchone()[0]
        
        return {
            'average_reputation': avg_reputation or 0.5,
            'total_partners': total_partners or 0,
            'strategy_usage': strategy_stats,
            'active_pools': active_pools,
            'cooperation_threshold': self.cooperation_threshold
        }