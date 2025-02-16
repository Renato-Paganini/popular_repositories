#Imports

from IPython.display import clear_output
import requests, datetime, time, os, csv
import seaborn as sns
import matplotlib.pyplot as plt

#Global variables

token = ""


#Querry 
def get_popular_repos(total_repos):
    url = "https://api.github.com/graphql"
    headers = {"Authorization": f"Bearer {token}"}
    all_repos = []
    end_cursor = None
    max_retries = 5
    retry_delay = 5

    while len(all_repos) < total_repos:
        remaining_repos = total_repos - len(all_repos)
        first = min(remaining_repos, 5)

        query = f"""
        {{
            search(query: "stars:>1", type: REPOSITORY, first: {first}, after: {f'"{end_cursor}"' if end_cursor else 'null'}) {{
                edges {{
                    node {{
                        ... on Repository {{
                            id
                            name
                            stargazers {{
                                totalCount
                            }}
                            forks {{
                                totalCount
                            }}
                            closedIssues: issues(states: [CLOSED]) {{
                                totalCount
                            }}
                            openIssues: issues(states: [OPEN]) {{
                                totalCount
                            }}
                            pullRequests {{
                                totalCount
                            }}
                            releases {{
                                totalCount
                            }}
                            pushedAt
                            createdAt
                            primaryLanguage {{
                                name
                            }}
                        }}
                    }}
                }}
                pageInfo {{
                    endCursor
                    hasNextPage
                }}
            }}
        }}
        """
        for attempt in range(max_retries):
            response = requests.post(url, json={'query': query}, headers=headers)
            if response.status_code == 200:
                data = response.json()
                search_results = data.get("data", {}).get("search", {})
                if search_results:
                    edges = search_results.get("edges", [])
                    all_repos.extend(edges)
                    end_cursor = search_results.get("pageInfo", {}).get("endCursor")
                    if not search_results.get("pageInfo", {}).get("hasNextPage", False):
                        return all_repos
                    print(f"Progress: Found {len(all_repos)} repositories.")
                break
            elif response.status_code in [502, 503, 504]:
                print(f"Error {response.status_code}: Attempt {attempt + 1} of {max_retries}. Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2
            elif response.status_code == 429:
                print("Rate limit exceeded. Waiting for the reset time.")
                reset_time = int(response.headers.get('X-RateLimit-Reset', time.time()))
                wait_time = max(reset_time - time.time(), 0)
                time.sleep(wait_time)
            else:
                raise Exception(f"Failed to fetch repositories: {response.status_code}")
        else:
            raise Exception("Max retries reached, aborting.")
    clear_output(wait=True)
    return all_repos


#Metrics
def calculate_average_age(repos):
    total_age = 0
    ages = []

    for repo_edge in repos:
        repo = repo_edge["node"]
        created_at = repo["createdAt"]
        creation_date = datetime.datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
        current_date = datetime.datetime.now()
        age_years = (current_date - creation_date).days / 365.25
        ages.append(age_years)
        total_age += age_years

    average_age = total_age / len(ages)
    above_average = len([age for age in ages if age > average_age])
    below_average = len([age for age in ages if age <= average_age])

    return average_age, above_average, below_average

def calculate_average_pr(repos):
    total_prs = 0
    prs_counts = []

    for repo_edge in repos:
        repo = repo_edge["node"]
        pr_count = repo["pullRequests"]["totalCount"]
        prs_counts.append(pr_count)
        total_prs += pr_count

    average_prs = total_prs / len(prs_counts)
    above_average = len([pr for pr in prs_counts if pr > average_prs])
    below_average = len([pr for pr in prs_counts if pr <= average_prs])

    return average_prs, above_average, below_average

def calculate_average_releases(repos):
    total_releases = 0
    releases_counts = []

    for repo_edge in repos:
        repo = repo_edge["node"]
        release_count = repo["releases"]["totalCount"]
        releases_counts.append(release_count)
        total_releases += release_count

    average_releases = total_releases / len(releases_counts)
    above_average = len([rel for rel in releases_counts if rel > average_releases])
    below_average = len([rel for rel in releases_counts if rel <= average_releases])

    return average_releases, above_average, below_average

def calculate_average_update_time(repos):
    total_update_time = 0
    update_times = []

    for repo_edge in repos:
        repo = repo_edge["node"]
        pushed_at = repo["pushedAt"]
        pushed_date = datetime.datetime.strptime(pushed_at, "%Y-%m-%dT%H:%M:%SZ")
        current_date = datetime.datetime.now()
        time_since_last_update = (current_date - pushed_date).days
        update_times.append(time_since_last_update)
        total_update_time += time_since_last_update

    average_update_time = total_update_time / len(update_times)
    above_average = len([ut for ut in update_times if ut < average_update_time])
    below_average = len([ut for ut in update_times if ut >= average_update_time])

    return average_update_time, above_average, below_average

def analyze_languages(repos, popular_languages):
    language_counts = {}
    for repo_edge in repos:
        repo = repo_edge["node"]
        language = repo["primaryLanguage"]["name"] if repo["primaryLanguage"] else "Unknown"
        if language not in language_counts:
            language_counts[language] = 0
        language_counts[language] += 1

    popular_language_counts = {lang: count for lang, count in language_counts.items() if lang in popular_languages}
    unknown_language_count = language_counts.get("Unknown", 0)

    total_repos = sum(language_counts.values())
    total_popular = sum(popular_language_counts.values())

    return language_counts, popular_language_counts, unknown_language_count, total_repos, total_popular

def calculate_issues_percentage(repos):
    total_open_issues = 0
    total_closed_issues = 0

    for repo_edge in repos:
        repo = repo_edge["node"]
        open_issues = repo["openIssues"]["totalCount"]
        closed_issues = repo["closedIssues"]["totalCount"]

        total_open_issues += open_issues
        total_closed_issues += closed_issues

    if total_open_issues + total_closed_issues > 0:
        closed_issues_percentage = (total_closed_issues / (total_open_issues + total_closed_issues)) * 100
    else:
        closed_issues_percentage = 0

    return closed_issues_percentage

# Summary
def collect_and_print_repo_info(repos):
    print("Analyzing...\n")
    average_age, above_average_age, below_average_age = calculate_average_age(repos)
    average_pull_requests, above_average_pull_requests, below_average_pull_requests = calculate_average_pr(repos)
    average_releases, above_average_releases, below_average_releases = calculate_average_releases(repos)
    average_update_time, above_average_update_time, below_average_update_time = calculate_average_update_time(repos)

    popular_languages = ["JavaScript", "Python", "Java", "TypeScript", "C#", "PHP", "Ruby", "Swift", "Go", "C++"]
    language_counts, popular_language_counts, unknown_language_count, total_repositories, total_popular_languages = analyze_languages(repos, popular_languages)

    closed_issues_percentage = calculate_issues_percentage(repos)

    os.system('clear')
    print("RQ1: ")
    print(f"Average age of repositories: {average_age:.2f} years")
    print(f"Repositories above average age: {above_average_age}")
    print(f"Repositories below or equal to average age: {below_average_age}\n")

    print("RQ2: ")
    print(f"Average merged pull requests: {average_pull_requests:.2f}")
    print(f"Repositories above average merged pull requests: {above_average_pull_requests}")
    print(f"Repositories below or equal to average merged pull requests: {below_average_pull_requests}\n")

    print("RQ3: ")
    print(f"Average number of releases: {average_releases:.2f}")
    print(f"Repositories above average releases: {above_average_releases}")
    print(f"Repositories below or equal to average releases: {below_average_releases}\n")

    print("RQ4: ")
    print(f"Average time since last update: {average_update_time:.2f} days")
    print(f"Repositories updated frequently (below average time): {above_average_update_time}")
    print(f"Repositories updated less frequently (time greater or equal to average): {below_average_update_time}\n")

    print("RQ 05: ")
    print(f"Total number of repositories analyzed: {total_repositories}")
    print(f"Total number of popular languages: {total_popular_languages}")
    print(f"Repositories using popular languages: {popular_language_counts}")
    print(f"Repositories using unpopular languages: {unknown_language_count}\n")

    print("RQ 06: ")
    print(f"Percentage of closed issues: {closed_issues_percentage:.2f}%\n")