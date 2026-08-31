import { useState } from "react";
import { searchtask } from "../services/taskService";
import { useTranslation } from "react-i18next";

function Search ()
{
	const [query, setquery] = useState("");
	const [status, setstatus] = useState("");
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
			const data = await searchtask(query, status);
			setresults(data.task);
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
			<h1>{t("random.recherche")}</h1>
			<form onSubmit={handlesearch} className="search-form">
				<input type="text" placeholder={t("random.recherche")} value={query} onChange={(e) => setquery(e.target.value)}/>
				<select value={status} onChange={(e) => setstatus(e.target.value)}>
					<option value="">{t("random.ttstatus")}</option>
					<option value="todo">{t("random.afaire")}</option>
					<option value="in_progress">{t("random.encours")}</option>
					<option value="done">{t("random.termine")}</option>
				</select>
				<button type="submit">{t("navbar.search")}</button>
			 </form>
			 {error && <p className="error">{error}</p>}
			 {loading && <p>{t("random.rechercheencours")}.</p>}

			 {error && <p className="error">{t("random.impossibleserv")}{error}</p>}

			 {!loading && !error && searched && results.length === 0 && (<p>{t("noresult")}</p>)}

			 <ul className="search-results">
				{
					results.map((task) =>
					<li key={task.id}>
						<h4>{task.title}</h4>
						<span className={`status-badge status-${task.status}`}>{task.status}</span>
					</li>
					)
				}
			 </ul>
		</div>
	);
}

export default Search;