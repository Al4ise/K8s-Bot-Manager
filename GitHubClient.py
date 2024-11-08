import requests
import git
import os
import logging

class GitHubClient:
    def __init__(self, personal_access_token, organization, team):
        self.personal_access_token = personal_access_token
        self.organization = organization
        self.team = team
        logging.basicConfig(level=logging.INFO)

    def get_repos(self):
        # GitHub API URL to fetch repositories from the specified organization and team
        url = f'https://api.github.com/orgs/{self.organization}/teams/{self.team}/repos'
        params = {
            'per_page': 100,
            'page': 1
        }

        # Set up headers for authentication
        headers = {
            'Authorization': f'token {self.personal_access_token}'
        }

        self.repo_urls = []

        # Loop to handle pagination
        while True:
            try:
                # Make the request to GitHub API
                response = requests.get(url, headers=headers, params=params)
                response.raise_for_status()

                # Parse the JSON response
                repos = response.json()

                if not repos:
                    break  # No more repos

                # Extract repository URLs
                self.repo_urls.extend([repo['clone_url'] for repo in repos])

                params['page'] += 1  # Increment page number
            except requests.exceptions.RequestException as e:
                logging.error(f'Failed to retrieve repositories: {e}')
                break

        return self.repo_urls
    
    def clone_repo(self, repo_url, base_directory):
        try:
            # Extract repository name from URL
            repo_name = repo_url.split('/')[-1].replace('.git', '')
            directory = os.path.join(base_directory, repo_name)

            if not os.path.exists(directory):
                os.makedirs(directory)
                auth_repo_url = repo_url.replace("https://", f"https://{self.personal_access_token}@")
                git.Repo.clone_from(auth_repo_url, directory)
                logging.info(f'Successfully cloned {repo_url} into {directory}')
            else:
                repo = git.Repo(directory)
                auth_repo_url = repo_url.replace("https://", f"https://{self.personal_access_token}@")
                origin = repo.remotes.origin
                origin.set_url(auth_repo_url)
                origin.pull()
                logging.info(f'Successfully pulled latest changes for {repo_url} in {directory}')
        except Exception as e:
            logging.error(f'Failed to clone/pull repository: {e}')