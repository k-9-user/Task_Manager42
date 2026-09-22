import { useState } from "react";
import { Link } from "react-router-dom";
import { searchtask } from "../services/taskService";
import { searchProjects } from "../services/projectService";
import { useTranslation } from "react-i18next";
import './Search.css';

function Search ()
{
	const [query, setquery] = useState("");
	const [status, setstatus] = useState("");
	const [searchType, setSearchType] = useState("tasks");
	const [sort, setSort] = useState("created_at");
	const [direction, setDirection] = useState("desc");
	const [results, setresults] = useState([]);
	const [loading, setloading] = useState(false);
	const [error, setError] = useState("");
	const [searched, setsearched] = useState(false);
	const { t } = useTranslation();

	async function handlesearch(e)
	{
		e.preventDefault();

		if (!query.trim())
		{
			setError(t("random.mrecherche"));
			return ;
		}
		setloading(true);
		setError("");
		setsearched(true);
		try
		{
			if (searchType === "projects")
			{
				const data = await searchProjects(query, sort, direction);
				setresults(data.projects);
			}
			else
			{
				const data = await searchtask(query, status, sort, direction);
				setresults(data.tasks);
			}
		}
		catch (err)
		{
			setError(err.message);
		}
		finally
		{
			setloading(false);
		}
	}
	return (
		<div className="Search-page">
			<h1>Task Manager</h1>
			<div className="Search-window">
				<div className="Search-titlebar">{t("random.recherche")}</div>
				<form onSubmit={handlesearch} className="search-form">
					<div className="input-group-search">
						<div className="input-field-search">
							<label htmlFor='search'>{t("random.recherche")} : </label>
							<input id="search" type="text" value={query} onChange={(e) => setquery(e.target.value)}/>
						</div>
						<select value={searchType} onChange={(e) => { setSearchType(e.target.value); setSort("created_at"); }}>
							<option value="tasks">Tâches</option>
							<option value="projects">Projets</option>
						</select>
						{searchType === "tasks" && (
							<select value={status} onChange={(e) => setstatus(e.target.value)}>
								<option value="">{t("random.ttstatus")}</option>
								<option value="todo">{t("random.afaire")}</option>
								<option value="in_progress">{t("random.encours")}</option>
								<option value="done">{t("random.termine")}</option>
							</select>
						)}
						<select value={sort} onChange={(e) => setSort(e.target.value)}>
							<option value="created_at">{t("random.tricreation")}</option>
							{searchType === "tasks" ? (
								<>
									<option value="title">{t("random.tritre")}</option>
									<option value="due_date">{t("random.triecheance")}</option>
									<option value="status">{t("random.tristatut")}</option>
								</>
							) : (
								<option value="name">{t("random.trinom")}</option>
							)}
						</select>
						<select value={direction} onChange={(e) => setDirection(e.target.value)}>
							<option value="desc">{t("random.tridesc")}</option>
							<option value="asc">{t("random.triasc")}</option>
						</select>
						<button type="submit">{t("navbar.search")}</button>
						{loading && <p>{t("random.rechercheencours")}.</p>}

						{error && <p className="error">{t("random.impossibleserv")}{error}</p>}

						{!loading && !error && searched && results.length === 0 && (<p>{t("random.noreult")}</p>)}
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
										<span className={`status-badge status-${task.status}`}>{task.status}</span>
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
