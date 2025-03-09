#Imports

from IPython.display import clear_output
import requests, datetime, time, os, csv
import seaborn as sns
import matplotlib.pyplot as plt

#Global variables

token = ""
csv_name = "result_file.csv"


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
def plot_boxplot(data, title, xlabel, ylabel):
    plt.figure(figsize=(10, 6))
    ax = sns.boxplot(data=data)
    mean_value = sum(data) / len(data)
    plt.scatter([0], [mean_value], color='red', zorder=5, label=f'Média: {mean_value:.2f}')
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.legend()
    plt.show()

def plot_language_ranking(language_counts):
    sorted_languages = sorted(language_counts.items(), key=lambda x: x[1], reverse=True)
    languages, counts = zip(*sorted_languages)
    plt.figure(figsize=(12, 8))
    sns.barplot(x=languages, y=counts, palette="Blues_d")
    plt.title("Ranking de Linguagens Populares por Número de Repositórios")
    plt.xlabel("Linguagem")
    plt.ylabel("Número de Repositórios")
    plt.xticks(rotation=45, ha="right")
    plt.show()

def plot_pie_chart(percentage_closed, percentage_open):
    labels = ['Issues Fechadas', 'Issues Abertas']
    sizes = [percentage_closed, percentage_open]
    colors = ['#ff9999','#66b3ff']
    plt.figure(figsize=(8, 8))
    plt.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=140, shadow=True)
    plt.title('Distribuição de Issues Fechadas e Abertas')
    plt.axis('equal')
    plt.show()


def collect_and_print_repo_info(repos):
    print("Analisando...\n")
    average_age, above_average, below_average = calculate_average_age(repos)
    average_prs, above_average_pr, below_average_pr = calculate_average_pr(repos)
    average_releases, above_release_avg, below_release_avg = calculate_average_releases(repos)
    average_update_time, above_update_avg, below_update_avg = calculate_average_update_time(repos)

    popular_languages = ["JavaScript", "Python", "Java", "TypeScript", "C#", "PHP", "Ruby", "Swift", "Go", "C++"]
    language_counts, popular_language_counts, unknown_language_count, total_repos, total_popular = analyze_languages(repos, popular_languages)

    closed_issues_percentage = calculate_issues_percentage(repos)

    os.system('clear')
    print("RQ1: ")
    print(f"Idade media dos repositorios: {average_age:.2f} anos")
    print(f"Repositorios acima da idade media: {above_average}")
    print(f"Repositorios abaixo ou igual a idade media: {below_average}\n")

    ages = [repo["node"]["createdAt"] for repo in repos]
    ages = [(datetime.datetime.now() - datetime.datetime.strptime(age, "%Y-%m-%dT%H:%M:%SZ")).days / 365.25 for age in ages]
    plot_boxplot(ages, "Distribuição da Idade dos Repositórios", "Idade (anos)", "Valor")

    print("RQ2: ")
    print(f"Media de PRs mergeados: {average_prs:.2f}")
    print(f"Repositorios acima da media de PRs mergeados: {above_average_pr}")
    print(f"Repositorios abaixo ou igual a media de PRs mergeados: {below_average_pr}\n")

    prs = [repo["node"]["pullRequests"]["totalCount"] for repo in repos]
    plot_boxplot(prs, "Distribuição do Número de PRs Mergeados", "Número de PRs", "Valor")

    print("RQ3: ")
    average_releases, above_release_avg, below_release_avg = calculate_average_releases(repos)
    print(f"Numero medio de releases: {average_releases:.2f}")
    print(f"Repositorios acima da media de releases: {above_release_avg}")
    print(f"Repositorios abaixo ou igual a media de releases: {below_release_avg}\n")
    releases = [repo["node"]["releases"]["totalCount"] for repo in repos]

    if len(releases) == 0:
        print("Nenhum dado de releases foi encontrado.")
    else:
        print(f"Número de releases encontrados: {len(releases)}")
        print(f"Dados de releases: {releases}")
        plot_boxplot(releases, "Distribuição do Número de Releases", "Número de Releases", "Valor")


    print("RQ4: ")
    average_update_time, above_update_avg, below_update_avg = calculate_average_update_time(repos)
    print(f"Tempo medio desde o ultimo update: {average_update_time:.2f} dias")
    print(f"Repositorios atualizados frequentemente (abaixo do tempo medio): {above_update_avg}")
    print(f"Repositorios atualizados mais raramente (tempo maior ou igual a media): {below_update_avg}\n")

    update_times = [(datetime.datetime.now() - datetime.datetime.strptime(repo["node"]["pushedAt"], "%Y-%m-%dT%H:%M:%SZ")).days for repo in repos]
    plot_boxplot(update_times, "Distribuição do Tempo desde o Último Update", "Tempo (dias)", "Valor")

    print("RQ 05: ")
    popular_languages = ["JavaScript", "Python", "Java", "TypeScript", "C#", "PHP", "Ruby", "Swift", "Go", "C++"]
    language_counts, popular_language_counts, unknown_language_count, total_repos, total_popular = analyze_languages(repos, popular_languages)

    print(f"Numero total de repositorios analisados: {total_repos}")
    print(f"Numero total de linguagens populares: {total_popular}")
    print(f"Repositorios utilizando linguagens populares: {popular_language_counts}")
    print(f"Repositorios utilizando linguagens impopulares: {unknown_language_count}\n")

    plot_language_ranking(language_counts)

    print("RQ 06: ")
    closed_issues_percentage = calculate_issues_percentage(repos)
    open_issues_percentage = 100 - closed_issues_percentage
    plot_pie_chart(closed_issues_percentage, open_issues_percentage)
    print(f"Porcentagem de issues fechadas: {closed_issues_percentage:.2f}%\n")


def export_to_csv(repos, filename="repos.csv"):
    with open(filename, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(["ID", "Name", "Stars", "Forks", "Open Issues", "Closed Issues", "PRs", "Releases", "Pushed At", "Created At", "Primary Language"])
        for repo_edge in repos:
            repo = repo_edge["node"]
            repo_id = repo["id"]
            name = repo["name"]
            stars = repo["stargazers"]["totalCount"]
            forks = repo["forks"]["totalCount"]
            open_issues = repo["openIssues"]["totalCount"]
            closed_issues = repo["closedIssues"]["totalCount"]
            prs = repo["pullRequests"]["totalCount"]
            releases = repo["releases"]["totalCount"]
            pushed_at = repo["pushedAt"]
            created_at = repo["createdAt"]
            primary_language = repo["primaryLanguage"]["name"] if repo["primaryLanguage"] else "Unknown"
            writer.writerow([repo_id, name, stars, forks, open_issues, closed_issues, prs, releases, pushed_at, created_at, primary_language])
    print(f"Dados exportados para {filename} com sucesso.")


def expose_data_with_pandas(filename="repos.csv"):
    try:
        df = pd.read_csv(filename)
        print("Primeiras linhas dos dados:")
        print(df.head())

        print("\nEstatísticas descritivas:")
        print(df.describe())

        print("\nInformações gerais dos dados:")
        print(df.info())

        print("\nDistribuição das estrelas (Stars):")
        df['Stars'].plot(kind='hist', bins=20, title='Distribuição das Estrelas (Stars)')
        plt.xlabel('Número de Stars')
        plt.ylabel('Frequência')
        plt.show()

    except Exception as e:
        print(f"Erro ao carregar os dados: {e}")


def get_all_repos(total):
  try:
      return get_popular_repos(total)
  except Exception as e:
      print(e)


def execute(total):
  try:
      repos = get_all_repos(total)
      collect_and_print_repo_info(get_all_repos(total))
      export_to_csv(repos, csv_name)
  except Exception as e:
      print(e)

execute(1000)
expose_data_with_pandas(csv_name)