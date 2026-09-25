import { useState } from "react";
import { Link } from "react-router-dom";
import { TASK_STATUSES, searchTasks } from "../services/taskService";
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
	const { t } = useTranslation();

	async function handleSearch(e)
	{
		e.preventDefault();

		if (!query.trim())
		{
			setError(t("search.queryRequired"));
			return ;
		}
		setLoading(true);
		setError("");
		setSearched(true);
		try
		{
			if (searchType === "projects")
			{
				const data = await searchProjects(query, sort, direction);
				setResults(data.projects);
			}
			else
			{
				const data = await searchTasks(query, status, sort, direction);
				setResults(data.tasks);
			}
		}
		catch (err)
		{
			setError(err.message);
		}
		finally
		{
			setLoading(false);
		}
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
						<select value={searchType} aria-label={t("search.typeLabel")} onChange={(e) => { setSearchType(e.target.value); setSort("created_at"); }}>
							<option value="tasks">{t("search.tasks")}</option>
							<option value="projects">{t("search.projects")}</option>
						</select>
						{searchType === "tasks" && (
							<select value={status} aria-label={t("tasks.statusLabel")} onChange={(e) => setStatus(e.target.value)}>
								<option value="">{t("search.allStatuses")}</option>
								{TASK_STATUSES.map((value) => (
									<option key={value} value={value}>{t(`tasks.status.${value}`)}</option>
								))}
							</select>
						)}
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
					</div>
				</form>
			</div>
		</div>
	);
}

export default Search;
