import os
import uuid
import logging
from GitConfig import GitConfig
from BotConfig import BotConfig
from BotManager import BotManager

# Configure logging
logger = logging.getLogger(__name__)

def create_bot_example():
    git_config = GitConfig(
        authentication_token=os.getenv("GITHUB_TOKEN"),
        organization_name="Lumiwealth-Strategies",
        team_name="lumiwealth-pro-plan-customers"
    )

    bot_config = BotConfig(
        user_id="user123",
        bot_id=str(uuid.uuid4()),
        broker="alpaca",
        repository_url="https://github.com/your-org/your-bot-repo.git",
    )

    bot_manager = BotManager()

    if bot_manager.is_authenticated_with_lumiwealth():
        logger.info("Authentication successful.")
    else:
        logger.error("Authentication failed.")
        return

    configuration = bot_config.resources
    if not bot_manager.validate_configuration(configuration):
        logger.error("Configuration validation failed.")
        return

    try:
        bot_id = bot_manager.add_bot(bot_config, git_config)
        logger.info(f"Bot '{bot_id}' successfully added.")
    except Exception as e:
        logger.error(f"An error occurred during bot deployment: {e}")
        return

    try:
        logs = bot_manager.get_bot_logs(bot_id)
        logger.info(f"Logs for bot '{bot_id}':\n{logs}")
    except Exception as e:
        logger.error(f"Failed to retrieve logs for bot '{bot_id}': {e}")

    try:
        bot_manager.remove_bot(bot_id)
        logger.info(f"Bot '{bot_id}' has been removed.")
    except Exception as e:
        logger.error(f"Failed to remove bot '{bot_id}': {e}")