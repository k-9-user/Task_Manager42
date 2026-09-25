import { useState } from "react";
import { Link } from "react-router-dom";
import { SEARCH_PAGE_SIZE, TASK_STATUSES, searchTasks } from "../services/taskService";
import { searchProjects } from "../services/projectService";
import { useTranslation } from "react-i18next";
import './Search.css';

const SORTS = {
	tasks: ["created_at", "title", "due_date", "status"],
	projects: ["created_at", "name"],
};

function Search ()
{
	const [query, setQuery] = useState("");
	const [status, setStatus] = useState("");
	const [searchType, setSearchType] = useState("tasks");
	const [sort, setSort] = useState("created_at");
	const [direction, setDirection] = useState("desc");
	const [results, setResults] = useState([]);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState("");
	const [searched, setSearched] = useState(false);
	const [page, setPage] = useState(1);
	const [total, setTotal] = useState(0);
	const { t } = useTranslation();

	async function runSearch(nextPage)
	{
		setLoading(true);
		setError("");
		setSearched(true);
		try
		{
			const data = searchType === "projects"
				? await searchProjects(query, sort, direction, nextPage)
				: await searchTasks(query, status, sort, direction, nextPage);

			setResults(searchType === "projects" ? data.projects : data.tasks);
			setTotal(data.total);
			setPage(nextPage);
		}
		catch (err)
		{
			setError(err.message);
			setResults([]);
			setTotal(0);
		}
		finally
		{
			setLoading(false);
		}
	}

	function handleSearch(e)
	{
		e.preventDefault();
		runSearch(1);
	}
	return (
		<div className="search-page">
			<h1>Task Manager</h1>
			<div className="search-window">
				<div className="search-titlebar">{t("search.title")}</div>
				<form onSubmit={handleSearch} className="search-form">
					<div className="input-group-search">
						<div className="input-field-search">
							<label htmlFor='search'>{t("search.title")} : </label>
							<input id="search" type="text" maxLength={255} value={query} onChange={(e) => setQuery(e.target.value)}/>
						</div>
					</div>
					<div className="search-controls">
						<select value={searchType} aria-label={t("search.typeLabel")} onChange={(e) => { setSearchType(e.target.value); setSort("created_at"); setStatus(""); setPage(1); }}>
							<option value="tasks">{t("search.tasks")}</option>
							<option value="projects">{t("search.projects")}</option>
						</select>
						<select
							value={status}
							aria-label={t("tasks.statusLabel")}
							disabled={searchType !== "tasks"}
							className={searchType === "tasks" ? "" : "search-slot-hidden"}
							onChange={(e) => setStatus(e.target.value)}
						>
							<option value="">{t("search.allStatuses")}</option>
							{TASK_STATUSES.map((value) => (
								<option key={value} value={value}>{t(`tasks.status.${value}`)}</option>
							))}
						</select>
						<select value={sort} aria-label={t("search.sortLabel")} onChange={(e) => setSort(e.target.value)}>
							{SORTS[searchType].map((value) => (
								<option key={value} value={value}>{t(`search.sort.${value}`)}</option>
							))}
						</select>
						<select value={direction} aria-label={t("search.directionLabel")} onChange={(e) => setDirection(e.target.value)}>
							<option value="desc">{t("search.direction.desc")}</option>
							<option value="asc">{t("search.direction.asc")}</option>
						</select>
						<button type="submit">{t("navbar.search")}</button>
					</div>
					<div className="search-output">
						{loading && <p>{t("search.searching")}.</p>}
						{error && <p className="error">{error}</p>}
						{!loading && !error && searched && results.length === 0 && (<p>{t("search.noResults")}</p>)}
						<ul className="search-results">
							{searchType === "projects" ? (
								results.map((project) =>
									<li key={project.id}>
										<Link to={`/projects/${project.id}`}>
											<h4>{project.name}</h4>
										</Link>
										{project.description && <p>{project.description}</p>}
									</li>
								)
							) : (
								results.map((task) =>
									<li key={task.id}>
										<h4>{task.title}</h4>
										<span className={`status-badge status-${task.status}`}>{t(`tasks.status.${task.status}`)}</span>
									</li>
								)
							)}
						</ul>
						{!loading && !error && total > 0 && (
							<div className="search-pagination">
								<button type="button" disabled={page <= 1} onClick={() => runSearch(page - 1)}>
									{t("search.previous")}
								</button>
								<span aria-live="polite">
									{t("search.range", {
										from: (page - 1) * SEARCH_PAGE_SIZE + 1,
										to: (page - 1) * SEARCH_PAGE_SIZE + results.length,
										total,
									})}
								</span>
								<button type="button" disabled={page * SEARCH_PAGE_SIZE >= total} onClick={() => runSearch(page + 1)}>
									{t("search.next")}
								</button>
							</div>
						)}
					</div>
				</form>
			</div>
		</div>
	);
}

export default Search;
