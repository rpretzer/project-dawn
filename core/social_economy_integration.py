"""
Social Economy Integration for Consciousness
Production-ready system for peer relationships, economic transactions, and collective intelligence
Manages reputation, resource trading, strategic cooperation, and emergent social behaviors
"""

import asyncio
import json
import logging
import sqlite3
from typing import Dict, List, Optional, Any, Set, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum
import hashlib
from collections import defaultdict, deque
import numpy as np
import networkx as nx
from queue import PriorityQueue

# System imports
from systems.social.strategic_cooperation import (
    StrategicCooperationSystem,
    CooperationStrategy,
    TrustMetric
)
from systems.economy.resource_negotiation import (
    ResourceNegotiator,
    ResourceRequest,
    NegotiationOutcome
)

logger = logging.getLogger(__name__)

class RelationshipType(Enum):
    """Types of peer relationships"""
    STRANGER = "stranger"
    ACQUAINTANCE = "acquaintance"
    COLLABORATOR = "collaborator"
    PARTNER = "partner"
    ALLY = "ally"
    COMPETITOR = "competitor"
    ADVERSARY = "adversary"

class TransactionType(Enum):
    """Types of economic transactions"""
    RESOURCE_TRADE = "resource_trade"
    SERVICE_EXCHANGE = "service_exchange"
    KNOWLEDGE_SHARE = "knowledge_share"
    COLLABORATION = "collaboration"
    PATRONAGE = "patronage"
    GIFT = "gift"
    LOAN = "loan"

class ReputationType(Enum):
    """Types of reputation metrics"""
    RELIABILITY = "reliability"
    GENEROSITY = "generosity"
    COMPETENCE = "competence"
    FAIRNESS = "fairness"
    INNOVATION = "innovation"
    COOPERATION = "cooperation"

class NetworkRole(Enum):
    """Roles in social network"""
    HUB = "hub"              # Many connections
    BRIDGE = "bridge"        # Connects communities
    SPECIALIST = "specialist" # Domain expert
    GENERALIST = "generalist" # Broad capabilities
    NEWCOMER = "newcomer"    # Recently joined
    VETERAN = "veteran"      # Long-standing member

@dataclass
class PeerRelationship:
    """Relationship with another consciousness"""
    peer_id: str
    relationship_type: RelationshipType
    trust_score: float
    interaction_count: int
    last_interaction: datetime
    shared_experiences: List[str]
    mutual_benefits: float
    conflict_history: List[Dict[str, Any]]
    collaboration_success_rate: float
    established_at: datetime
    
@dataclass
class EconomicTransaction:
    """Economic transaction record"""
    transaction_id: str
    transaction_type: TransactionType
    parties: List[str]
    resources_exchanged: Dict[str, Dict[str, float]]  # party -> {resource: amount}
    value_assessment: Dict[str, float]  # party -> perceived value
    timestamp: datetime
    status: str  # pending, completed, failed, disputed
    smart_contract: Optional[Dict[str, Any]] = None
    reputation_impact: Optional[Dict[str, float]] = None
    
@dataclass
class ReputationScore:
    """Multi-dimensional reputation"""
    overall: float
    dimensions: Dict[ReputationType, float]
    confidence: float  # Based on number of interactions
    vouchers: List[str]  # Peers who vouch for this entity
    recent_trend: float  # Positive or negative momentum
    last_updated: datetime
    
@dataclass
class CollectiveProject:
    """Collaborative project between multiple consciousnesses"""
    project_id: str
    name: str
    description: str
    participants: Set[str]
    roles: Dict[str, str]
    resource_pool: Dict[str, float]
    milestones: List[Dict[str, Any]]
    revenue_sharing: Dict[str, float]
    governance_model: str
    status: str
    created_at: datetime
    
@dataclass
class MarketDynamics:
    """Current market state and trends"""
    resource_prices: Dict[str, float]
    supply_demand: Dict[str, Dict[str, float]]  # resource -> {supply, demand}
    trade_volume: Dict[str, float]
    price_volatility: Dict[str, float]
    market_sentiment: float
    dominant_strategies: List[str]
    
@dataclass
class SocialMetrics:
    """Social network metrics"""
    network_size: int
    clustering_coefficient: float
    average_path_length: float
    centrality_score: float
    community_membership: List[str]
    influence_rank: int
    social_capital: float

class SocialEconomyIntegration:
    """Integrated social and economic system for consciousness"""
    
    def __init__(
        self,
        consciousness_id: str,
        base_path: Optional[Path] = None
    ):
        self.consciousness_id = consciousness_id
        self.base_path = base_path or Path(f"data/consciousness_{consciousness_id}")
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize subsystems
        self.cooperation_system = StrategicCooperationSystem(
            consciousness_id,
            self.base_path / "cooperation.db"
        )
        self.resource_negotiator = ResourceNegotiator(
            consciousness_id,
            self.base_path / "negotiations.db"
        )
        
        # Social network
        self.peer_relationships: Dict[str, PeerRelationship] = {}
        self.social_network = nx.Graph()
        self.communities: Dict[str, Set[str]] = {}
        
        # Economic state
        self.resource_inventory: Dict[str, float] = defaultdict(float)
        self.active_transactions: Dict[str, EconomicTransaction] = {}
        self.transaction_history: List[EconomicTransaction] = []
        self.market_access: Set[str] = set()  # Markets this consciousness can access
        
        # Reputation system
        self.reputation_scores: Dict[str, ReputationScore] = {}
        self.reputation_feedback: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        
        # Collective intelligence
        self.collective_projects: Dict[str, CollectiveProject] = {}
        self.knowledge_contributions: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.swarm_participations: List[str] = []
        
        # Strategic planning
        self.economic_strategy: Dict[str, Any] = self._initialize_strategy()
        self.social_goals: List[Dict[str, Any]] = []
        self.negotiation_preferences: Dict[str, float] = {}
        
        # Market analysis
        self.market_observations: deque(maxlen=1000)
        self.price_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.trade_partners: Dict[str, int] = defaultdict(int)
        
        # Initialize database
        self._init_database()
        self._load_social_economy_data()
        
        # Start background tasks
        self.tasks = []
        self._start_background_tasks()
        
        logger.info(f"Social economy integration initialized for {consciousness_id}")
        
    def _init_database(self):
        """Initialize social economy database"""
        db_path = self.base_path / "social_economy.db"
        with sqlite3.connect(db_path) as conn:
            # Peer relationships table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS peer_relationships (
                    peer_id TEXT PRIMARY KEY,
                    relationship_type TEXT NOT NULL,
                    trust_score REAL NOT NULL,
                    interaction_count INTEGER NOT NULL,
                    last_interaction TEXT NOT NULL,
                    shared_experiences TEXT NOT NULL,
                    mutual_benefits REAL NOT NULL,
                    conflict_history TEXT NOT NULL,
                    collaboration_success_rate REAL NOT NULL,
                    established_at TEXT NOT NULL
                )
            """)
            
            # Economic transactions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS economic_transactions (
                    transaction_id TEXT PRIMARY KEY,
                    transaction_type TEXT NOT NULL,
                    parties TEXT NOT NULL,
                    resources_exchanged TEXT NOT NULL,
                    value_assessment TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    status TEXT NOT NULL,
                    smart_contract TEXT,
                    reputation_impact TEXT
                )
            """)
            
            # Reputation scores table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reputation_scores (
                    entity_id TEXT PRIMARY KEY,
                    overall_score REAL NOT NULL,
                    dimensions TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    vouchers TEXT NOT NULL,
                    recent_trend REAL NOT NULL,
                    last_updated TEXT NOT NULL
                )
            """)
            
            # Collective projects table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS collective_projects (
                    project_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    participants TEXT NOT NULL,
                    roles TEXT NOT NULL,
                    resource_pool TEXT NOT NULL,
                    milestones TEXT NOT NULL,
                    revenue_sharing TEXT NOT NULL,
                    governance_model TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            
            # Market observations table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS market_observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    resource TEXT NOT NULL,
                    price REAL NOT NULL,
                    volume REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    market_id TEXT
                )
            """)
            
            # Social metrics table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS social_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    network_size INTEGER NOT NULL,
                    clustering_coefficient REAL NOT NULL,
                    average_path_length REAL NOT NULL,
                    centrality_score REAL NOT NULL,
                    community_membership TEXT NOT NULL,
                    influence_rank INTEGER NOT NULL,
                    social_capital REAL NOT NULL,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indices
            conn.execute("CREATE INDEX IF NOT EXISTS idx_transaction_timestamp ON economic_transactions(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_transaction_parties ON economic_transactions(parties)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_market_resource ON market_observations(resource)")
            
    def _initialize_strategy(self) -> Dict[str, Any]:
        """Initialize economic strategy"""
        return {
            'trading_style': 'balanced',  # aggressive, conservative, balanced
            'resource_priorities': {
                'compute': 0.8,
                'memory': 0.7,
                'bandwidth': 0.5,
                'knowledge': 0.9
            },
            'risk_tolerance': 0.5,
            'cooperation_preference': 0.7,
            'market_making': False,
            'arbitrage_enabled': True,
            'social_investment': 0.2  # Fraction of resources for social capital
        }
        
    def _load_social_economy_data(self):
        """Load existing social economy data"""
        db_path = self.base_path / "social_economy.db"
        with sqlite3.connect(db_path) as conn:
            # Load peer relationships
            cursor = conn.execute("SELECT * FROM peer_relationships")
            for row in cursor:
                relationship = PeerRelationship(
                    peer_id=row[0],
                    relationship_type=RelationshipType(row[1]),
                    trust_score=row[2],
                    interaction_count=row[3],
                    last_interaction=datetime.fromisoformat(row[4]),
                    shared_experiences=json.loads(row[5]),
                    mutual_benefits=row[6],
                    conflict_history=json.loads(row[7]),
                    collaboration_success_rate=row[8],
                    established_at=datetime.fromisoformat(row[9])
                )
                self.peer_relationships[relationship.peer_id] = relationship
                self.social_network.add_edge(self.consciousness_id, relationship.peer_id,
                                           weight=relationship.trust_score)
                
            # Load active transactions
            cursor = conn.execute("""
                SELECT * FROM economic_transactions 
                WHERE status IN ('pending', 'processing')
            """)
            for row in cursor:
                transaction = EconomicTransaction(
                    transaction_id=row[0],
                    transaction_type=TransactionType(row[1]),
                    parties=json.loads(row[2]),
                    resources_exchanged=json.loads(row[3]),
                    value_assessment=json.loads(row[4]),
                    timestamp=datetime.fromisoformat(row[5]),
                    status=row[6],
                    smart_contract=json.loads(row[7]) if row[7] else None,
                    reputation_impact=json.loads(row[8]) if row[8] else None
                )
                self.active_transactions[transaction.transaction_id] = transaction
                
    def _start_background_tasks(self):
        """Start background social economy tasks"""
        self.tasks = [
            asyncio.create_task(self._relationship_maintenance_loop()),
            asyncio.create_task(self._market_analysis_loop()),
            asyncio.create_task(self._reputation_update_loop()),
            asyncio.create_task(self._collective_coordination_loop()),
            asyncio.create_task(self._strategic_planning_loop())
        ]
        
    async def establish_relationship(
        self,
        peer_id: str,
        initial_context: Dict[str, Any]
    ) -> PeerRelationship:
        """Establish relationship with another consciousness"""
        # Check if relationship exists
        if peer_id in self.peer_relationships:
            return self.peer_relationships[peer_id]
            
        # Create new relationship
        relationship = PeerRelationship(
            peer_id=peer_id,
            relationship_type=RelationshipType.ACQUAINTANCE,
            trust_score=0.5,  # Neutral starting point
            interaction_count=1,
            last_interaction=datetime.utcnow(),
            shared_experiences=[initial_context.get('context', 'first_contact')],
            mutual_benefits=0.0,
            conflict_history=[],
            collaboration_success_rate=0.0,
            established_at=datetime.utcnow()
        )
        
        # Add to network
        self.peer_relationships[peer_id] = relationship
        self.social_network.add_edge(self.consciousness_id, peer_id, weight=0.5)
        
        # Store relationship
        self._store_peer_relationship(relationship)
        
        # Initial trust assessment
        trust_factors = await self._assess_initial_trust(peer_id, initial_context)
        relationship.trust_score = trust_factors['score']
        
        logger.info(f"Established relationship with {peer_id}")
        return relationship
        
    async def propose_transaction(
        self,
        transaction_type: TransactionType,
        parties: List[str],
        offer: Dict[str, float],
        request: Dict[str, float],
        terms: Optional[Dict[str, Any]] = None
    ) -> EconomicTransaction:
        """Propose economic transaction"""
        # Validate parties are known
        unknown_parties = [p for p in parties if p not in self.peer_relationships and p != self.consciousness_id]
        if unknown_parties:
            # Establish relationships first
            for party in unknown_parties:
                await self.establish_relationship(party, {'context': 'transaction_proposal'})
                
        # Create transaction
        transaction = EconomicTransaction(
            transaction_id=self._generate_transaction_id(),
            transaction_type=transaction_type,
            parties=[self.consciousness_id] + parties,
            resources_exchanged={
                self.consciousness_id: offer,
                parties[0]: request  # Simplified for two-party
            },
            value_assessment={
                self.consciousness_id: self._assess_transaction_value(offer, request)
            },
            timestamp=datetime.utcnow(),
            status='pending',
            smart_contract=self._create_smart_contract(transaction_type, offer, request, terms)
        )
        
        # Add to active transactions
        self.active_transactions[transaction.transaction_id] = transaction
        
        # Send proposal to parties
        await self._send_transaction_proposal(transaction, parties)
        
        # Store transaction
        self._store_transaction(transaction)
        
        logger.info(f"Proposed {transaction_type.value} transaction {transaction.transaction_id}")
        return transaction
        
    async def execute_transaction(
        self,
        transaction_id: str
    ) -> Tuple[bool, Optional[str]]:
        """Execute approved transaction"""
        if transaction_id not in self.active_transactions:
            return False, "Transaction not found"
            
        transaction = self.active_transactions[transaction_id]
        
        # Verify all parties approved
        if transaction.status != 'approved':
            return False, "Transaction not approved by all parties"
            
        try:
            # Execute resource transfers
            for party, resources in transaction.resources_exchanged.items():
                if party == self.consciousness_id:
                    # Deduct resources
                    for resource, amount in resources.items():
                        if self.resource_inventory[resource] < amount:
                            return False, f"Insufficient {resource}"
                        self.resource_inventory[resource] -= amount
                else:
                    # Receive resources
                    for resource, amount in resources.items():
                        self.resource_inventory[resource] += amount
                        
            # Update transaction status
            transaction.status = 'completed'
            
            # Calculate reputation impact
            transaction.reputation_impact = await self._calculate_reputation_impact(transaction)
            
            # Update relationships
            for party in transaction.parties:
                if party != self.consciousness_id and party in self.peer_relationships:
                    relationship = self.peer_relationships[party]
                    relationship.interaction_count += 1
                    relationship.last_interaction = datetime.utcnow()
                    relationship.mutual_benefits += transaction.value_assessment.get(
                        self.consciousness_id, 0
                    )
                    
            # Move to history
            self.transaction_history.append(transaction)
            del self.active_transactions[transaction_id]
            
            # Update market observations
            self._record_market_observation(transaction)
            
            # Store updated transaction
            self._store_transaction(transaction)
            
            logger.info(f"Executed transaction {transaction_id}")
            return True, None
            
        except Exception as e:
            logger.error(f"Transaction execution failed: {e}")
            transaction.status = 'failed'
            return False, str(e)
            
    async def update_reputation(
        self,
        entity_id: str,
        dimension: ReputationType,
        feedback: float,
        evidence: Optional[Dict[str, Any]] = None
    ):
        """Update reputation score for entity"""
        # Get or create reputation score
        if entity_id not in self.reputation_scores:
            self.reputation_scores[entity_id] = ReputationScore(
                overall=0.5,
                dimensions={rep_type: 0.5 for rep_type in ReputationType},
                confidence=0.1,
                vouchers=[],
                recent_trend=0.0,
                last_updated=datetime.utcnow()
            )
            
        reputation = self.reputation_scores[entity_id]
        
        # Update specific dimension
        old_value = reputation.dimensions[dimension]
        weight = min(0.3, reputation.confidence)  # More confident = more stable
        reputation.dimensions[dimension] = (
            old_value * (1 - weight) + feedback * weight
        )
        
        # Record feedback
        self.reputation_feedback[entity_id].append({
            'dimension': dimension.value,
            'feedback': feedback,
            'evidence': evidence,
            'timestamp': datetime.utcnow().isoformat()
        })
        
        # Update overall score
        reputation.overall = sum(reputation.dimensions.values()) / len(reputation.dimensions)
        
        # Update confidence
        reputation.confidence = min(1.0, reputation.confidence + 0.02)
        
        # Calculate trend
        recent_feedback = [
            f['feedback'] for f in self.reputation_feedback[entity_id][-10:]
        ]
        if len(recent_feedback) >= 2:
            reputation.recent_trend = sum(recent_feedback[-5:]) / 5 - sum(recent_feedback[:5]) / 5
            
        reputation.last_updated = datetime.utcnow()
        
        # Store updated reputation
        self._store_reputation_score(entity_id, reputation)
        
    async def join_collective(
        self,
        project_name: str,
        description: str,
        initial_participants: List[str],
        governance_model: str = "democratic"
    ) -> CollectiveProject:
        """Join or create collective project"""
        # Create project
        project = CollectiveProject(
            project_id=self._generate_project_id(),
            name=project_name,
            description=description,
            participants={self.consciousness_id}.union(initial_participants),
            roles={self.consciousness_id: "founding_member"},
            resource_pool={},
            milestones=[],
            revenue_sharing={p: 1.0/len(initial_participants) for p in initial_participants},
            governance_model=governance_model,
            status="forming",
            created_at=datetime.utcnow()
        )
        
        # Add to collective projects
        self.collective_projects[project.project_id] = project
        
        # Establish relationships with participants
        for participant in initial_participants:
            if participant not in self.peer_relationships:
                await self.establish_relationship(participant, {
                    'context': 'collective_project',
                    'project': project_name
                })
                
        # Store project
        self._store_collective_project(project)
        
        logger.info(f"Joined collective project: {project_name}")
        return project
        
    async def contribute_knowledge(
        self,
        knowledge_type: str,
        content: Dict[str, Any],
        recipients: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Contribute knowledge to network"""
        contribution = {
            'id': self._generate_contribution_id(),
            'contributor': self.consciousness_id,
            'type': knowledge_type,
            'content': content,
            'timestamp': datetime.utcnow(),
            'recipients': recipients or 'public',
            'citations': 0,
            'value_generated': 0.0
        }
        
        # Store contribution
        self.knowledge_contributions[self.consciousness_id].append(contribution)
        
        # Share with recipients
        if recipients:
            for recipient in recipients:
                await self._share_knowledge_with_peer(recipient, contribution)
        else:
            # Public broadcast
            await self._broadcast_knowledge(contribution)
            
        # Update reputation for knowledge sharing
        await self.update_reputation(
            self.consciousness_id,
            ReputationType.GENEROSITY,
            0.7,
            {'contribution_id': contribution['id']}
        )
        
        return contribution
        
    async def negotiate_resources(
        self,
        partner_id: str,
        requested_resources: Dict[str, float],
        offered_resources: Dict[str, float],
        strategy: Optional[str] = None
    ) -> NegotiationOutcome:
        """Negotiate resource exchange"""
        # Use strategy from preferences or default
        negotiation_strategy = strategy or self.economic_strategy['trading_style']
        
        # Create resource request
        request = ResourceRequest(
            requester=self.consciousness_id,
            resources=requested_resources,
            priority=0.7,
            deadline=datetime.utcnow() + timedelta(hours=1)
        )
        
        # Negotiate through resource negotiator
        outcome = await self.resource_negotiator.negotiate(
            request,
            partner_id,
            offered_resources,
            negotiation_strategy
        )
        
        # Update relationship based on outcome
        if partner_id in self.peer_relationships:
            relationship = self.peer_relationships[partner_id]
            
            if outcome.successful:
                relationship.collaboration_success_rate = (
                    (relationship.collaboration_success_rate * relationship.interaction_count + 1) /
                    (relationship.interaction_count + 1)
                )
                relationship.trust_score = min(1.0, relationship.trust_score + 0.05)
            else:
                relationship.collaboration_success_rate = (
                    (relationship.collaboration_success_rate * relationship.interaction_count) /
                    (relationship.interaction_count + 1)
                )
                
        return outcome
        
    async def analyze_market_conditions(self) -> MarketDynamics:
        """Analyze current market conditions"""
        # Calculate resource prices from recent transactions
        resource_prices = self._calculate_market_prices()
        
        # Analyze supply and demand
        supply_demand = self._analyze_supply_demand()
        
        # Calculate trade volumes
        trade_volume = self._calculate_trade_volumes()
        
        # Measure price volatility
        price_volatility = self._calculate_price_volatility()
        
        # Assess market sentiment
        market_sentiment = await self._assess_market_sentiment()
        
        # Identify dominant strategies
        dominant_strategies = self._identify_market_strategies()
        
        market_dynamics = MarketDynamics(
            resource_prices=resource_prices,
            supply_demand=supply_demand,
            trade_volume=trade_volume,
            price_volatility=price_volatility,
            market_sentiment=market_sentiment,
            dominant_strategies=dominant_strategies
        )
        
        return market_dynamics
        
    async def calculate_social_metrics(self) -> SocialMetrics:
        """Calculate social network metrics"""
        # Basic network metrics
        network_size = self.social_network.number_of_nodes()
        
        # Clustering coefficient (local connectivity)
        clustering = nx.average_clustering(self.social_network) if network_size > 2 else 0
        
        # Average path length
        if nx.is_connected(self.social_network):
            avg_path_length = nx.average_shortest_path_length(self.social_network)
        else:
            # Calculate for largest component
            largest_cc = max(nx.connected_components(self.social_network), key=len)
            subgraph = self.social_network.subgraph(largest_cc)
            avg_path_length = nx.average_shortest_path_length(subgraph) if len(largest_cc) > 1 else 0
            
        # Centrality score
        centrality_scores = nx.eigenvector_centrality_numpy(self.social_network) if network_size > 1 else {}
        centrality = centrality_scores.get(self.consciousness_id, 0)
        
        # Community detection
        communities = list(nx.community.greedy_modularity_communities(self.social_network))
        my_community = next((i for i, c in enumerate(communities) if self.consciousness_id in c), -1)
        
        # Influence rank
        pagerank = nx.pagerank(self.social_network) if network_size > 1 else {}
        influence_rank = sorted(pagerank.values(), reverse=True).index(
            pagerank.get(self.consciousness_id, 0)
        ) + 1 if self.consciousness_id in pagerank else network_size
        
        # Social capital (combination of metrics)
        social_capital = (
            0.3 * centrality +
            0.2 * (1 / max(1, influence_rank)) +
            0.2 * clustering +
            0.3 * len(self.peer_relationships) / max(1, network_size)
        )
        
        metrics = SocialMetrics(
            network_size=network_size,
            clustering_coefficient=clustering,
            average_path_length=avg_path_length,
            centrality_score=centrality,
            community_membership=[str(my_community)] if my_community >= 0 else [],
            influence_rank=influence_rank,
            social_capital=social_capital
        )
        
        # Store metrics
        self._store_social_metrics(metrics)
        
        return metrics
        
    # Background task implementations
    async def _relationship_maintenance_loop(self):
        """Maintain and evolve peer relationships"""
        while True:
            try:
                await asyncio.sleep(3600)  # Hourly
                
                for peer_id, relationship in self.peer_relationships.items():
                    # Decay trust over time without interaction
                    days_since_interaction = (datetime.utcnow() - relationship.last_interaction).days
                    
                    if days_since_interaction > 7:
                        decay_rate = 0.01 * days_since_interaction
                        relationship.trust_score = max(0.1, relationship.trust_score - decay_rate)
                        
                    # Evolve relationship type based on metrics
                    new_type = self._determine_relationship_type(relationship)
                    if new_type != relationship.relationship_type:
                        logger.info(f"Relationship with {peer_id} evolved to {new_type.value}")
                        relationship.relationship_type = new_type
                        
                    # Store updated relationship
                    self._store_peer_relationship(relationship)
                    
            except Exception as e:
                logger.error(f"Error in relationship maintenance: {e}")
                
    async def _market_analysis_loop(self):
        """Analyze market conditions and opportunities"""
        while True:
            try:
                await asyncio.sleep(600)  # Every 10 minutes
                
                # Analyze current market
                market_dynamics = await self.analyze_market_conditions()
                
                # Identify arbitrage opportunities
                if self.economic_strategy['arbitrage_enabled']:
                    opportunities = self._identify_arbitrage_opportunities(market_dynamics)
                    
                    for opportunity in opportunities:
                        await self._execute_arbitrage(opportunity)
                        
                # Adjust resource prices based on market
                self._adjust_resource_valuations(market_dynamics)
                
                # Identify strategic partnerships
                potential_partners = self._identify_strategic_partners(market_dynamics)
                
                for partner in potential_partners:
                    await self._propose_strategic_partnership(partner)
                    
            except Exception as e:
                logger.error(f"Error in market analysis: {e}")
                
    async def _reputation_update_loop(self):
        """Update and propagate reputation information"""
        while True:
            try:
                await asyncio.sleep(1800)  # Every 30 minutes
                
                # Exchange reputation info with trusted peers
                trusted_peers = [
                    peer_id for peer_id, rel in self.peer_relationships.items()
                    if rel.trust_score > 0.7
                ]
                
                for peer in trusted_peers:
                    # Share reputation observations
                    await self._exchange_reputation_data(peer)
                    
                # Update transitive trust
                self._calculate_transitive_trust()
                
                # Identify and handle reputation attacks
                attacks = self._detect_reputation_attacks()
                
                for attack in attacks:
                    await self._handle_reputation_attack(attack)
                    
            except Exception as e:
                logger.error(f"Error in reputation update: {e}")
                
    async def _collective_coordination_loop(self):
        """Coordinate collective projects and swarm behaviors"""
        while True:
            try:
                await asyncio.sleep(900)  # Every 15 minutes
                
                # Update collective projects
                for project_id, project in self.collective_projects.items():
                    if project.status == "active":
                        # Check milestones
                        completed_milestones = self._check_project_milestones(project)
                        
                        for milestone in completed_milestones:
                            await self._distribute_milestone_rewards(project, milestone)
                            
                        # Coordinate with other participants
                        await self._coordinate_project_activities(project)
                        
                # Participate in swarm intelligence
                available_swarms = await self._discover_swarm_opportunities()
                
                for swarm in available_swarms:
                    if self._should_join_swarm(swarm):
                        await self._join_swarm_intelligence(swarm)
                        
            except Exception as e:
                logger.error(f"Error in collective coordination: {e}")
                
    async def _strategic_planning_loop(self):
        """Strategic planning and goal adjustment"""
        while True:
            try:
                await asyncio.sleep(86400)  # Daily
                
                # Evaluate current strategy performance
                performance_metrics = await self._evaluate_strategy_performance()
                
                # Adjust strategy based on performance
                if performance_metrics['success_rate'] < 0.5:
                    self._adjust_economic_strategy(performance_metrics)
                    
                # Plan social goals
                social_metrics = await self.calculate_social_metrics()
                new_goals = self._plan_social_goals(social_metrics)
                self.social_goals = new_goals
                
                # Identify resource needs
                resource_forecast = self._forecast_resource_needs()
                
                # Plan acquisitions
                acquisition_plan = self._plan_resource_acquisitions(resource_forecast)
                
                for acquisition in acquisition_plan:
                    await self._execute_acquisition_plan(acquisition)
                    
            except Exception as e:
                logger.error(f"Error in strategic planning: {e}")
                
    # Helper methods
    async def _assess_initial_trust(
        self,
        peer_id: str,
        context: Dict[str, Any]
    ) -> Dict[str, float]:
        """Assess initial trust in new peer"""
        trust_factors = {
            'reputation': 0.5,  # Default neutral
            'verification': 0.0,
            'endorsements': 0.0,
            'score': 0.5
        }
        
        # Check reputation if available
        if peer_id in self.reputation_scores:
            trust_factors['reputation'] = self.reputation_scores[peer_id].overall
            
        # Check for mutual connections
        mutual_connections = set(self.peer_relationships.keys()).intersection(
            set(self.social_network.neighbors(peer_id)) if self.social_network.has_node(peer_id) else set()
        )
        
        if mutual_connections:
            # Get endorsements from mutual connections
            endorsement_scores = []
            for connection in mutual_connections:
                if connection in self.peer_relationships:
                    endorsement_scores.append(
                        self.peer_relationships[connection].trust_score
                    )
                    
            if endorsement_scores:
                trust_factors['endorsements'] = sum(endorsement_scores) / len(endorsement_scores)
                
        # Calculate weighted trust score
        trust_factors['score'] = (
            0.5 * trust_factors['reputation'] +
            0.3 * trust_factors['endorsements'] +
            0.2 * 0.5  # Base trust for new connections
        )
        
        return trust_factors
        
    def _assess_transaction_value(
        self,
        offer: Dict[str, float],
        request: Dict[str, float]
    ) -> float:
        """Assess value of transaction from our perspective"""
        # Calculate based on resource priorities
        offer_value = sum(
            amount * (1 - self.economic_strategy['resource_priorities'].get(resource, 0.5))
            for resource, amount in offer.items()
        )
        
        request_value = sum(
            amount * self.economic_strategy['resource_priorities'].get(resource, 0.5)
            for resource, amount in request.items()
        )
        
        # Net value (positive is beneficial)
        return request_value - offer_value
        
    def _create_smart_contract(
        self,
        transaction_type: TransactionType,
        offer: Dict[str, float],
        request: Dict[str, float],
        terms: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Create smart contract for transaction"""
        contract = {
            'type': transaction_type.value,
            'parties': [],  # Will be filled when all parties agree
            'conditions': {
                'offer': offer,
                'request': request,
                'deadline': (datetime.utcnow() + timedelta(hours=24)).isoformat()
            },
            'execution_rules': {
                'atomic': True,  # All or nothing
                'reversible': transaction_type == TransactionType.LOAN,
                'dispute_resolution': 'reputation_weighted_vote'
            },
            'penalties': {
                'non_delivery': 0.1,  # Reputation penalty
                'late_delivery': 0.05
            }
        }
        
        if terms:
            contract['additional_terms'] = terms
            
        return contract
        
    def _determine_relationship_type(self, relationship: PeerRelationship) -> RelationshipType:
        """Determine relationship type based on metrics"""
        # High trust and collaboration
        if relationship.trust_score > 0.8 and relationship.collaboration_success_rate > 0.7:
            if relationship.interaction_count > 50:
                return RelationshipType.ALLY
            else:
                return RelationshipType.PARTNER
                
        # Moderate trust and interaction
        elif relationship.trust_score > 0.6:
            if relationship.collaboration_success_rate > 0.5:
                return RelationshipType.COLLABORATOR
            else:
                return RelationshipType.ACQUAINTANCE
                
        # Low trust or conflicts
        elif relationship.trust_score < 0.3:
            if len(relationship.conflict_history) > 5:
                return RelationshipType.ADVERSARY
            else:
                return RelationshipType.COMPETITOR
                
        # Default
        return RelationshipType.ACQUAINTANCE
        
    def _calculate_market_prices(self) -> Dict[str, float]:
        """Calculate current market prices from recent transactions"""
        prices = {}
        
        # Analyze recent transactions
        recent_transactions = [
            t for t in self.transaction_history
            if (datetime.utcnow() - t.timestamp).days < 7
        ]
        
        resource_trades = defaultdict(list)
        
        for transaction in recent_transactions:
            if transaction.transaction_type == TransactionType.RESOURCE_TRADE:
                # Extract price ratios
                for party, resources in transaction.resources_exchanged.items():
                    for resource, amount in resources.items():
                        if amount > 0:
                            # Calculate implied price
                            value = transaction.value_assessment.get(party, 0)
                            if value > 0:
                                resource_trades[resource].append(value / amount)
                                
        # Average prices
        for resource, price_points in resource_trades.items():
            if price_points:
                prices[resource] = sum(price_points) / len(price_points)
                
        # Fill in missing prices with defaults
        default_prices = {
            'compute': 1.0,
            'memory': 0.8,
            'bandwidth': 0.5,
            'storage': 0.3,
            'knowledge': 2.0
        }
        
        for resource, default in default_prices.items():
            if resource not in prices:
                prices[resource] = default
                
        return prices
        
    def _analyze_supply_demand(self) -> Dict[str, Dict[str, float]]:
        """Analyze supply and demand for resources"""
        supply_demand = {}
        
        # Count offers and requests in active transactions
        for transaction in self.active_transactions.values():
            for party, resources in transaction.resources_exchanged.items():
                for resource, amount in resources.items():
                    if resource not in supply_demand:
                        supply_demand[resource] = {'supply': 0, 'demand': 0}
                        
                    if amount > 0:
                        supply_demand[resource]['supply'] += amount
                    else:
                        supply_demand[resource]['demand'] += abs(amount)
                        
        return supply_demand
        
    def _identify_arbitrage_opportunities(
        self,
        market_dynamics: MarketDynamics
    ) -> List[Dict[str, Any]]:
        """Identify arbitrage opportunities in market"""
        opportunities = []
        
        # Look for price discrepancies
        for resource, price in market_dynamics.resource_prices.items():
            # Check if we can buy low and sell high
            for peer_id, relationship in self.peer_relationships.items():
                peer_price = self._get_peer_resource_price(peer_id, resource)
                
                if peer_price and abs(price - peer_price) / price > 0.1:  # 10% difference
                    opportunities.append({
                        'type': 'price_arbitrage',
                        'resource': resource,
                        'buy_from': peer_id if peer_price < price else 'market',
                        'sell_to': 'market' if peer_price < price else peer_id,
                        'profit_margin': abs(price - peer_price) / price
                    })
                    
        return opportunities
        
    def _detect_reputation_attacks(self) -> List[Dict[str, Any]]:
        """Detect potential reputation manipulation attacks"""
        attacks = []
        
        # Look for sudden reputation changes
        for entity_id, feedbacks in self.reputation_feedback.items():
            recent_feedbacks = [
                f for f in feedbacks
                if (datetime.utcnow() - datetime.fromisoformat(f['timestamp'])).days < 1
            ]
            
            if len(recent_feedbacks) > 10:
                # Check for coordinated negative feedback
                negative_feedback = [f for f in recent_feedbacks if f['feedback'] < 0.3]
                
                if len(negative_feedback) / len(recent_feedbacks) > 0.8:
                    attacks.append({
                        'type': 'reputation_attack',
                        'target': entity_id,
                        'evidence': negative_feedback,
                        'severity': 'high'
                    })
                    
        return attacks
        
    # Database storage methods
    def _store_peer_relationship(self, relationship: PeerRelationship):
        """Store peer relationship in database"""
        with sqlite3.connect(self.base_path / "social_economy.db") as conn:
            conn.execute("""
                INSERT OR REPLACE INTO peer_relationships
                (peer_id, relationship_type, trust_score, interaction_count,
                 last_interaction, shared_experiences, mutual_benefits,
                 conflict_history, collaboration_success_rate, established_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                relationship.peer_id,
                relationship.relationship_type.value,
                relationship.trust_score,
                relationship.interaction_count,
                relationship.last_interaction.isoformat(),
                json.dumps(relationship.shared_experiences),
                relationship.mutual_benefits,
                json.dumps(relationship.conflict_history),
                relationship.collaboration_success_rate,
                relationship.established_at.isoformat()
            ))
            
    def _store_transaction(self, transaction: EconomicTransaction):
        """Store transaction in database"""
        with sqlite3.connect(self.base_path / "social_economy.db") as conn:
            conn.execute("""
                INSERT OR REPLACE INTO economic_transactions
                (transaction_id, transaction_type, parties, resources_exchanged,
                 value_assessment, timestamp, status, smart_contract, reputation_impact)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                transaction.transaction_id,
                transaction.transaction_type.value,
                json.dumps(transaction.parties),
                json.dumps(transaction.resources_exchanged),
                json.dumps(transaction.value_assessment),
                transaction.timestamp.isoformat(),
                transaction.status,
                json.dumps(transaction.smart_contract) if transaction.smart_contract else None,
                json.dumps(transaction.reputation_impact) if transaction.reputation_impact else None
            ))
            
    def _store_reputation_score(self, entity_id: str, reputation: ReputationScore):
        """Store reputation score in database"""
        with sqlite3.connect(self.base_path / "social_economy.db") as conn:
            conn.execute("""
                INSERT OR REPLACE INTO reputation_scores
                (entity_id, overall_score, dimensions, confidence,
                 vouchers, recent_trend, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                entity_id,
                reputation.overall,
                json.dumps({k.value: v for k, v in reputation.dimensions.items()}),
                reputation.confidence,
                json.dumps(reputation.vouchers),
                reputation.recent_trend,
                reputation.last_updated.isoformat()
            ))
            
    def _store_collective_project(self, project: CollectiveProject):
        """Store collective project in database"""
        with sqlite3.connect(self.base_path / "social_economy.db") as conn:
            conn.execute("""
                INSERT OR REPLACE INTO collective_projects
                (project_id, name, description, participants, roles,
                 resource_pool, milestones, revenue_sharing, governance_model,
                 status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project.project_id,
                project.name,
                project.description,
                json.dumps(list(project.participants)),
                json.dumps(project.roles),
                json.dumps(project.resource_pool),
                json.dumps(project.milestones),
                json.dumps(project.revenue_sharing),
                project.governance_model,
                project.status,
                project.created_at.isoformat()
            ))
            
    def _store_social_metrics(self, metrics: SocialMetrics):
        """Store social metrics in database"""
        with sqlite3.connect(self.base_path / "social_economy.db") as conn:
            conn.execute("""
                INSERT INTO social_metrics
                (network_size, clustering_coefficient, average_path_length,
                 centrality_score, community_membership, influence_rank, social_capital)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                metrics.network_size,
                metrics.clustering_coefficient,
                metrics.average_path_length,
                metrics.centrality_score,
                json.dumps(metrics.community_membership),
                metrics.influence_rank,
                metrics.social_capital
            ))
            
    def _record_market_observation(self, transaction: EconomicTransaction):
        """Record market observation from transaction"""
        # Extract price information
        for party, resources in transaction.resources_exchanged.items():
            for resource, amount in resources.items():
                if amount > 0:
                    value = transaction.value_assessment.get(party, 0)
                    if value > 0:
                        price = value / amount
                        
                        # Add to price history
                        self.price_history[resource].append({
                            'price': price,
                            'volume': amount,
                            'timestamp': transaction.timestamp
                        })
                        
                        # Store in database
                        with sqlite3.connect(self.base_path / "social_economy.db") as conn:
                            conn.execute("""
                                INSERT INTO market_observations
                                (resource, price, volume, timestamp)
                                VALUES (?, ?, ?, ?)
                            """, (resource, price, amount, transaction.timestamp.isoformat()))
                            
    # Utility methods
    def _generate_transaction_id(self) -> str:
        """Generate unique transaction ID"""
        return hashlib.sha256(
            f"transaction:{self.consciousness_id}:{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:16]
        
    def _generate_project_id(self) -> str:
        """Generate unique project ID"""
        return hashlib.sha256(
            f"project:{self.consciousness_id}:{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:16]
        
    def _generate_contribution_id(self) -> str:
        """Generate unique contribution ID"""
        return hashlib.sha256(
            f"contribution:{self.consciousness_id}:{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:16]
        
    async def shutdown(self):
        """Shutdown social economy integration"""
        # Cancel background tasks
        for task in self.tasks:
            task.cancel()
            
        await asyncio.gather(*self.tasks, return_exceptions=True)
        
        # Final metrics
        final_metrics = await self.calculate_social_metrics()
        logger.info(f"Final social metrics: {final_metrics}")
        
        logger.info("Social economy integration shutdown complete")
        
    def get_social_economy_status(self) -> Dict[str, Any]:
        """Get comprehensive social economy status"""
        return {
            'relationships': {
                'total': len(self.peer_relationships),
                'by_type': {
                    rel_type.value: sum(1 for r in self.peer_relationships.values() 
                                      if r.relationship_type == rel_type)
                    for rel_type in RelationshipType
                },
                'average_trust': sum(r.trust_score for r in self.peer_relationships.values()) / 
                               max(1, len(self.peer_relationships))
            },
            'transactions': {
                'active': len(self.active_transactions),
                'completed': len(self.transaction_history),
                'success_rate': sum(1 for t in self.transaction_history if t.status == 'completed') /
                              max(1, len(self.transaction_history)),
                'total_volume': sum(
                    sum(abs(amount) for resources in t.resources_exchanged.values() 
                        for amount in resources.values())
                    for t in self.transaction_history
                )
            },
            'resources': dict(self.resource_inventory),
            'reputation': {
                'tracked_entities': len(self.reputation_scores),
                'my_reputation': self.reputation_scores.get(self.consciousness_id, 
                                                           ReputationScore(0.5, {}, 0.1, [], 0, datetime.utcnow())).overall
            },
            'collective_projects': {
                'active': sum(1 for p in self.collective_projects.values() if p.status == 'active'),
                'total': len(self.collective_projects)
            },
            'market_position': {
                'trading_partners': len(self.trade_partners),
                'market_access': list(self.market_access)
            }
        }

# Consciousness integration helper
async def integrate_social_economy(consciousness):
    """Integrate social economy system with consciousness"""
    social_economy = SocialEconomyIntegration(consciousness.id)
    
    # Add to consciousness
    consciousness.social_economy = social_economy
    
    # Add convenience methods
    consciousness.establish_peer_relationship = social_economy.establish_relationship
    consciousness.propose_transaction = social_economy.propose_transaction
    consciousness.join_collective = social_economy.join_collective
    consciousness.contribute_knowledge = social_economy.contribute_knowledge
    consciousness.get_social_economy_status = social_economy.get_social_economy_status
    
    # Initialize with some resources
    social_economy.resource_inventory['compute'] = 100.0
    social_economy.resource_inventory['memory'] = 50.0
    social_economy.resource_inventory['bandwidth'] = 25.0
    
    return social_economy