from GitHubClient import GitHubClient

# instructions to get the access token: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens

access_token = "" # token needs 'Full control of private repositories' permission

organization = "Lumiwealth-Strategies"
team = "lumiwealth-pro-plan-customers"
authenticator = GitHubClient(access_token, organization, team)

# get repos
authenticator.get_repos()
repo_urls = authenticator.repo_urls

# to make into a gui probably
print("Pick a repository:")
for i, repo in enumerate(repo_urls, start=1):
    repo_name = repo.split('/')[-1].replace('.git', '')
    print(f"{i}. {repo_name}")

choice = int(input("Enter the number of the repository you want to pick: "))
selected_repo = repo_urls[choice - 1]

print(f"You picked: {selected_repo}")

# clone chosen repo
authenticator.clone_repo(selected_repo, "./repos")
