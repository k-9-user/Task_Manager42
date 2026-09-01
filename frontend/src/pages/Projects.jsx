import { useState, useEffect } from "react";
import { getProjects, createProject } from "../services/projectService";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";


const USE_MOCK = true;

const mockProjects = [
	{ id: "1", name: "site vitrine", description: "Refonte du site client"},
];

function Projects()
{
	const [projects, setProjects] = useState([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState("");
	const [name, setName] = useState("");
	const [description, setDescription] = useState("");
	const { t } = useTranslation();

	useEffect(() =>
	{
		async function fetchProjects() {
		try
		{
			if (USE_MOCK)
			{
				setProjects(mockProjects);
			}
			else
			{
				const data = await getProjects();
				setProjects(data.projects);
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
	fetchProjects();
	}, []);

	async function handleCreate(e)
	{
		e.preventDefault();

		if (!name.trim()) {
			setError(t("random.nameproject"));
			return;
		}
		try
		{
			if (USE_MOCK) {
				const newProject = { id: Date.now().toString(), name, description };
				setProjects([...projects, newProject]);
			}
			else
			{
				const data = await createProject(name, description);
				setProjects([...projects, data.project]);
			}
			setName("");
			setDescription("");
			setError("");
		}
		catch (err)
		{
			setError(err.message);
		}
	}

	if (loading)
		return <p>{t("loading.load")}</p>;

	return (
		<div className="projects-page">
			<h1>Projets</h1>
			{error && <p className="error">{error}</p>}
			<form onSubmit={handleCreate} className="project-form">
				<input type="text" placeholder={t("projects.namePlaceholder")} value={name} onChange={(e) => setName(e.target.value)} />
				<input type="text" placeholder={t("projects.description")} value={description} onChange={(e) => setDescription(e.target.value)} />
				<button type="submit">{t("projects.create")}</button>
			</form>
			<ul className="project-list">
				{projects.map((project) => (
					<li key={project.id}>
						<Link to={`/projects/${project.id}`}>
							<h3>{project.name}</h3>
						</Link>
						<p>{project.description}</p>
					</li>
				))}
			</ul>
		</div>
	);
}

export default Projects;