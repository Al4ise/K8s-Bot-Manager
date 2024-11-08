from typing import Optional
import logging
from GitHubClient import GitHubClient

logger = logging.getLogger(__name__)

class GitConfig:
    def __init__(self, authentication_token: str, repo_path: str = "./repos",
                 repository_url: str = "https://github.com/your-org/your-bot-repo.git",
                 organization_name: str = "your-org",
                 team_name: str = "your-team"):
        self.authentication_token = authentication_token
        self.repo_path = repo_path
        self.organization_name = organization_name
        self.team_name = team_name

    def clone_repository(self, repository_url) -> Optional[str]:
        try:
            authenticator = GitHubClient(
                self.authentication_token,
                self.organization_name,
                self.team_name
            )
            repository_path = authenticator.clone_repo(repository_url, self.repo_path)
            if repository_path:
                logger.info(f"Repository cloned to {repository_path}")
                return repository_path
            else:
                logger.error("Failed to clone repository.")
                return None
        except Exception as e:
            logger.error(f"Error cloning repository: {e}")
            return None