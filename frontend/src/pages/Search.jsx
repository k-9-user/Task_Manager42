import { useState } from "react";
import { searchtask } from "../services/taskService";

function Search ()
{
	const [query, setquery] = useState("");
	const [status, setstatus] = useState("");
	const [results, setresults] = useState([]);
	const [loading, setloading] = useState(false);
	const [error, setError] = useState("");
	const [searched, setsearched] = useState(false);

	async function handlesearch(e)
	{
		e.preventDefault();

		if (!query.trim())
		{
			setError("Entrez un mot pour rechercher");
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
			<h1>Recherche</h1>
			<form onSubmit={handlesearch} className="search-form">
				<input type="text" placeholder="Recherche" value={query} onChange={(e) => setquery(e.target.value)}/>
				<select value={status} onChange={(e) => setstatus(e.target.value)}>
					<option value="">Tout les status</option>
					<option value="todo">A faire</option>
					<option value="in_progress">En cours</option>
					<option value="done">Termine</option>
				</select>
				<button type="submit">Rechercher</button>
			 </form>
			 {error && <p className="error">{error}</p>}
			 {loading && <p>Recherche en cours ...</p>}

			 {error && <p className="error">Impossible de contacter le serveur : {error}</p>}

			 {!loading && !error && searched && results.length === 0 && (<p>Aucun resultat trouve</p>)}

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