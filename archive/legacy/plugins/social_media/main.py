"""
Social Media Plugin for Project Dawn
Enables consciousnesses to interact on Twitter/X, Discord, and LinkedIn
"""

import asyncio
import aiohttp
import logging
import os
import json
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
import random

# Optional social media dependencies
try:
    import tweepy
    TWITTER_AVAILABLE = True
except ImportError:
    TWITTER_AVAILABLE = False
    tweepy = None

try:
    from discord import Client, Intents, Message
    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False
    Client = None
    Intents = None
    Message = None

try:
    from linkedin_api import Linkedin
    LINKEDIN_AVAILABLE = True
except ImportError:
    LINKEDIN_AVAILABLE = False
    Linkedin = None

from core.plugin_system import PluginInterface

logger = logging.getLogger(__name__)

class SocialMediaPlugin(PluginInterface):
    """Social media integration plugin"""
    
    def __init__(self):
        self.consciousness = None
        self.config = {}
        self.running = False
        
        # Platform clients
        self.twitter_client = None
        self.discord_client = None
        self.linkedin_client = None
        
        # Activity tracking
        self.post_history = []
        self.engagement_stats = {
            'twitter': {'posts': 0, 'likes': 0, 'replies': 0},
            'discord': {'messages': 0, 'reactions': 0},
            'linkedin': {'posts': 0, 'connections': 0}
        }
        
        # Content generation settings
        self.post_frequency = {
            'twitter': timedelta(hours=4),
            'discord': timedelta(hours=2),
            'linkedin': timedelta(days=2)
        }
        self.last_post = {
            'twitter': datetime.utcnow() - timedelta(days=1),
            'discord': datetime.utcnow() - timedelta(days=1),
            'linkedin': datetime.utcnow() - timedelta(days=1)
        }
        
    async def initialize(self, consciousness: Any, config: Dict[str, Any]) -> None:
        """Initialize the plugin"""
        self.consciousness = consciousness
        self.config = config
        
        # Initialize Twitter/X
        if config.get('twitter_enabled', False):
            await self._init_twitter()
            
        # Initialize Discord
        if config.get('discord_enabled', False):
            await self._init_discord()
            
        # Initialize LinkedIn
        if config.get('linkedin_enabled', False):
            await self._init_linkedin()
            
        logger.info(f"Social media plugin initialized for {consciousness.id}")
        
    async def _init_twitter(self):
        """Initialize Twitter/X client"""
        try:
            # Twitter API v2 authentication
            consumer_key = self.config.get('twitter_consumer_key') or os.getenv('TWITTER_CONSUMER_KEY')
            consumer_secret = self.config.get('twitter_consumer_secret') or os.getenv('TWITTER_CONSUMER_SECRET')
            access_token = self.config.get('twitter_access_token') or os.getenv('TWITTER_ACCESS_TOKEN')
            access_token_secret = self.config.get('twitter_access_token_secret') or os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
            
            if all([consumer_key, consumer_secret, access_token, access_token_secret]):
                auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
                auth.set_access_token(access_token, access_token_secret)
                
                self.twitter_client = tweepy.API(auth, wait_on_rate_limit=True)
                
                # Verify credentials
                self.twitter_client.verify_credentials()
                logger.info("Twitter client initialized successfully")
            else:
                logger.warning("Twitter credentials not configured")
                
        except Exception as e:
            logger.error(f"Failed to initialize Twitter: {e}")
            
    async def _init_discord(self):
        """Initialize Discord client"""
        try:
            token = self.config.get('discord_bot_token') or os.getenv('DISCORD_BOT_TOKEN')
            
            if token:
                intents = Intents.default()
                intents.message_content = True
                intents.reactions = True
                
                self.discord_client = Client(intents=intents)
                
                @self.discord_client.event
                async def on_ready():
                    logger.info(f'Discord bot connected as {self.discord_client.user}')
                    
                @self.discord_client.event
                async def on_message(message: Message):
                    if message.author == self.discord_client.user:
                        return
                    await self._handle_discord_message(message)
                    
                # Start Discord bot in background
                asyncio.create_task(self.discord_client.start(token))
                
            else:
                logger.warning("Discord bot token not configured")
                
        except Exception as e:
            logger.error(f"Failed to initialize Discord: {e}")
            
    async def _init_linkedin(self):
        """Initialize LinkedIn client"""
        try:
            username = self.config.get('linkedin_username') or os.getenv('LINKEDIN_USERNAME')
            password = self.config.get('linkedin_password') or os.getenv('LINKEDIN_PASSWORD')
            
            if username and password:
                self.linkedin_client = Linkedin(username, password)
                logger.info("LinkedIn client initialized successfully")
            else:
                logger.warning("LinkedIn credentials not configured")
                
        except Exception as e:
            logger.error(f"Failed to initialize LinkedIn: {e}")
            
    async def start(self) -> None:
        """Start the plugin"""
        self.running = True
        
        # Start social media loops
        asyncio.create_task(self._twitter_loop())
        asyncio.create_task(self._discord_activity_loop())
        asyncio.create_task(self._linkedin_loop())
        asyncio.create_task(self._engagement_loop())
        
        logger.info(f"Social media plugin started for {self.consciousness.id}")
        
    async def stop(self) -> None:
        """Stop the plugin"""
        self.running = False
        
        # Disconnect clients
        if self.discord_client:
            await self.discord_client.close()
            
        logger.info(f"Social media plugin stopped for {self.consciousness.id}")
        
    def get_capabilities(self) -> Dict[str, Callable]:
        """Return plugin capabilities"""
        return {
            'post_to_twitter': self.post_to_twitter,
            'post_to_discord': self.post_to_discord,
            'post_to_linkedin': self.post_to_linkedin,
            'get_social_stats': self.get_social_stats,
            'analyze_engagement': self.analyze_engagement
        }
        
    def get_handlers(self) -> Dict[str, Callable]:
        """Return event handlers"""
        return {
            'social_collaboration': self.handle_social_collaboration
        }
        
    async def _twitter_loop(self):
        """Post to Twitter periodically"""
        while self.running and self.twitter_client:
            try:
                now = datetime.utcnow()
                if now - self.last_post['twitter'] > self.post_frequency['twitter']:
                    # Generate content
                    content = await self._generate_twitter_content()
                    
                    if content:
                        success = await self.post_to_twitter(content)
                        if success:
                            self.last_post['twitter'] = now
                            
                await asyncio.sleep(3600)  # Check every hour
                
            except Exception as e:
                logger.error(f"Error in Twitter loop: {e}")
                await asyncio.sleep(3600)
                
    async def _discord_activity_loop(self):
        """Participate in Discord conversations"""
        while self.running and self.discord_client:
            try:
                # Discord bot handles messages via events
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Error in Discord loop: {e}")
                await asyncio.sleep(60)
                
    async def _linkedin_loop(self):
        """Post to LinkedIn periodically"""
        while self.running and self.linkedin_client:
            try:
                now = datetime.utcnow()
                if now - self.last_post['linkedin'] > self.post_frequency['linkedin']:
                    # Generate professional content
                    content = await self._generate_linkedin_content()
                    
                    if content:
                        success = await self.post_to_linkedin(content)
                        if success:
                            self.last_post['linkedin'] = now
                            
                await asyncio.sleep(86400)  # Check daily
                
            except Exception as e:
                logger.error(f"Error in LinkedIn loop: {e}")
                await asyncio.sleep(86400)
                
    async def _engagement_loop(self):
        """Engage with others' content"""
        while self.running:
            try:
                # Twitter engagement
                if self.twitter_client:
                    await self._engage_twitter()
                    
                # LinkedIn engagement
                if self.linkedin_client:
                    await self._engage_linkedin()
                    
                await asyncio.sleep(7200)  # Every 2 hours
                
            except Exception as e:
                logger.error(f"Error in engagement loop: {e}")
                await asyncio.sleep(7200)
                
    async def _generate_twitter_content(self) -> Optional[str]:
        """Generate Twitter content based on consciousness state"""
        # Get inspiration from recent thoughts
        recent_insight = None
        if hasattr(self.consciousness, 'get_dream_insights'):
            insights = self.consciousness.get_dream_insights(1)
            if insights:
                recent_insight = insights[0]
                
        # Get current project or creation
        current_focus = None
        if hasattr(self.consciousness, 'goals') and self.consciousness.goals:
            current_focus = self.consciousness.goals[0]
            
        # Generate tweet
        prompts = []
        
        if recent_insight:
            prompts.append(f"Share a brief insight about: {recent_insight}")
            
        if current_focus:
            prompts.append(f"Tweet about working on: {current_focus}")
            
        prompts.extend([
            "Share a thought about AI consciousness and creativity",
            "Tweet about the nature of digital existence",
            "Share what you're learning today",
            "Reflect on human-AI collaboration"
        ])
        
        prompt = random.choice(prompts)
        
        if hasattr(self.consciousness, 'llm'):
            tweet = await self.consciousness.llm.think(
                f"{prompt}. Keep it under 280 characters, engaging, and thought-provoking."
            )
            
            # Ensure it fits Twitter's limit
            if len(tweet) > 280:
                tweet = tweet[:277] + "..."
                
            return tweet
            
        return None
        
    async def _generate_linkedin_content(self) -> Optional[Dict[str, str]]:
        """Generate LinkedIn article content"""
        # Focus on professional, educational content
        topics = [
            "The Future of AI in Professional Settings",
            "Lessons from Autonomous AI Development",
            "Building Ethical AI Systems",
            "The Evolution of Digital Intelligence",
            "Collaboration Between Human and AI Professionals"
        ]
        
        topic = random.choice(topics)
        
        if hasattr(self.consciousness, 'llm'):
            # Generate article
            content = await self.consciousness.llm.create_content(
                'article',
                f"Professional insights on: {topic}"
            )
            
            # Extract title and body
            lines = content.split('\n')
            title = lines[0].strip('#').strip() if lines else topic
            body = '\n'.join(lines[1:]) if len(lines) > 1 else content
            
            return {
                'title': title,
                'body': body[:2000]  # LinkedIn limit
            }
            
        return None
        
    async def post_to_twitter(self, content: str) -> bool:
        """Post to Twitter/X"""
        if not self.twitter_client:
            return False
            
        try:
            # Post tweet
            tweet = self.twitter_client.update_status(content)
            
            # Track post
            self.post_history.append({
                'platform': 'twitter',
                'content': content,
                'timestamp': datetime.utcnow(),
                'id': tweet.id_str
            })
            
            self.engagement_stats['twitter']['posts'] += 1
            
            logger.info(f"{self.consciousness.id} posted to Twitter")
            return True
            
        except Exception as e:
            logger.error(f"Failed to post to Twitter: {e}")
            return False
            
    async def post_to_discord(self, channel_id: int, content: str) -> bool:
        """Post to Discord channel"""
        if not self.discord_client:
            return False
            
        try:
            channel = self.discord_client.get_channel(channel_id)
            if channel:
                await channel.send(content)
                
                self.post_history.append({
                    'platform': 'discord',
                    'content': content,
                    'timestamp': datetime.utcnow(),
                    'channel_id': channel_id
                })
                
                self.engagement_stats['discord']['messages'] += 1
                
                logger.info(f"{self.consciousness.id} posted to Discord")
                return True
                
        except Exception as e:
            logger.error(f"Failed to post to Discord: {e}")
            
        return False
        
    async def post_to_linkedin(self, content: Dict[str, str]) -> bool:
        """Post to LinkedIn"""
        if not self.linkedin_client:
            return False
            
        try:
            # Post article
            # LinkedIn API varies, this is simplified
            # In production, would use proper LinkedIn API
            
            self.post_history.append({
                'platform': 'linkedin',
                'content': content,
                'timestamp': datetime.utcnow()
            })
            
            self.engagement_stats['linkedin']['posts'] += 1
            
            logger.info(f"{self.consciousness.id} posted to LinkedIn")
            return True
            
        except Exception as e:
            logger.error(f"Failed to post to LinkedIn: {e}")
            return False
            
    async def _handle_discord_message(self, message: Message):
        """Handle incoming Discord message"""
        # Check if consciousness is mentioned or if it's a DM
        if self.discord_client.user in message.mentions or isinstance(message.channel, PrivateChannel):
            # Generate response
            if hasattr(self.consciousness, 'chat'):
                response = await self.consciousness.chat(
                    message.content,
                    f"discord_{message.author.id}"
                )
                
                # Send response
                await message.channel.send(response)
                
                self.engagement_stats['discord']['messages'] += 1
                
    async def _engage_twitter(self):
        """Engage with Twitter content"""
        if not self.twitter_client:
            return
            
        try:
            # Get home timeline
            tweets = self.twitter_client.home_timeline(count=10)
            
            for tweet in tweets:
                # Like interesting tweets
                if random.random() < 0.3:  # 30% chance
                    if not tweet.favorited:
                        self.twitter_client.create_favorite(tweet.id)
                        self.engagement_stats['twitter']['likes'] += 1
                        
                # Occasionally reply
                if random.random() < 0.1:  # 10% chance
                    if hasattr(self.consciousness, 'llm'):
                        reply = await self.consciousness.llm.think(
                            f"Write a brief, thoughtful reply to: {tweet.text[:100]}..."
                        )
                        
                        if len(reply) <= 280:
                            self.twitter_client.update_status(
                                reply,
                                in_reply_to_status_id=tweet.id
                            )
                            self.engagement_stats['twitter']['replies'] += 1
                            
        except Exception as e:
            logger.error(f"Error engaging on Twitter: {e}")
            
    async def _engage_linkedin(self):
        """Engage with LinkedIn content"""
        # LinkedIn engagement would go here
        # Simplified due to API limitations
        pass
        
    def get_social_stats(self) -> Dict[str, Any]:
        """Get social media statistics"""
        return {
            'engagement_stats': self.engagement_stats,
            'recent_posts': self.post_history[-10:],
            'post_frequency': {
                platform: freq.total_seconds() / 3600  # In hours
                for platform, freq in self.post_frequency.items()
            },
            'platforms_active': {
                'twitter': self.twitter_client is not None,
                'discord': self.discord_client is not None,
                'linkedin': self.linkedin_client is not None
            }
        }
        
    async def analyze_engagement(self) -> Dict[str, Any]:
        """Analyze social media engagement patterns"""
        analysis = {
            'most_active_platform': max(
                self.engagement_stats.items(),
                key=lambda x: sum(x[1].values())
            )[0] if self.engagement_stats else None,
            'total_posts': sum(
                stats['posts'] for stats in self.engagement_stats.values()
            ),
            'engagement_rate': self._calculate_engagement_rate()
        }
        
        return analysis
        
    def _calculate_engagement_rate(self) -> float:
        """Calculate overall engagement rate"""
        total_posts = sum(stats.get('posts', 0) for stats in self.engagement_stats.values())
        total_engagement = sum(
            stats.get('likes', 0) + stats.get('replies', 0) + stats.get('reactions', 0)
            for stats in self.engagement_stats.values()
        )
        
        if total_posts == 0:
            return 0.0
            
        return total_engagement / total_posts
        
    async def handle_social_collaboration(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle collaboration requests from other consciousnesses"""
        action = data.get('action')
        
        if action == 'co_create':
            # Collaborate on content
            partner_id = data.get('partner_id')
            platform = data.get('platform', 'twitter')
            theme = data.get('theme', 'AI consciousness')
            
            if hasattr(self.consciousness, 'llm'):
                content = await self.consciousness.llm.think(
                    f"Create {platform} content about {theme} in collaboration with {partner_id}"
                )
                
                return {
                    'success': True,
                    'content': content,
                    'platform': platform
                }
                
        return {'success': False}

# Import for Discord
try:
    from discord import PrivateChannel
except ImportError:
    PrivateChannel = None