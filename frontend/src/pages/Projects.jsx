import { useState, useEffect } from "react";
import { getProjects, createProject } from "../services/projectService";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";


function Projects()
{
	const [projects, setProjects] = useState([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState("");
	const [name, setName] = useState("");
	const [description, setDescription] = useState("");
	const [showForm, setShowForm] = useState(false);
	const { t } = useTranslation();

	useEffect(() =>
	{
		async function fetchProjects() {
		try
		{
			const data = await getProjects();
			setProjects(data.projects);
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
			setError(t("projects.nameRequired"));
			return;
		}
		try
		{
			const data = await createProject(name, description);
			setProjects([...projects, data.project]);
			setName("");
			setDescription("");
			setError("");
			setShowForm(false);
		}
		catch (err)
		{
			setError(err.message);
		}
	}

	if (loading)
		return <p>{t("loading.load")}</p>;

	return (
		<div className="flex min-h-full flex-col gap-6 bg-brand-surface-alt p-8 font-sans max-sm:p-4">
			<div className="flex flex-wrap items-center justify-between gap-4">
				<h1 className="m-0 text-brand-primary-darker">{t("projects.title")}</h1>
				<button
					className="cursor-pointer rounded-lg border-none bg-brand-primary px-5 py-2.5 text-sm font-semibold text-white hover:bg-brand-primary-hover"
					onClick={() => setShowForm(!showForm)}
				>
					{showForm ? t("register.return") : `+ ${t("projects.create")}`}
				</button>
			</div>
			{error && <p className="m-0 rounded-lg bg-red-100 px-3 py-2 text-sm text-red-700">{error}</p>}
			{showForm && (
				<form onSubmit={handleCreate} className="flex flex-wrap gap-2.5 rounded-xl border border-brand-surface-border bg-brand-surface p-4">
					<input
						type="text"
						placeholder={t("projects.namePlaceholder")}
						value={name}
						onChange={(e) => setName(e.target.value)}
						className="min-w-40 flex-1 rounded-md border border-brand-surface-border px-2.5 py-2 text-sm"
					/>
					<input
						type="text"
						placeholder={t("projects.description")}
						value={description}
						onChange={(e) => setDescription(e.target.value)}
						className="min-w-40 flex-1 rounded-md border border-brand-surface-border px-2.5 py-2 text-sm"
					/>
					<button type="submit" className="cursor-pointer rounded-md border-none bg-brand-primary px-4 py-2 text-sm font-semibold text-white hover:bg-brand-primary-hover">
						{t("projects.create")}
					</button>
				</form>
			)}
			<div className="grid grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-5">
				{projects.map((project) => (
					<Link
						to={`/projects/${project.id}`}
						key={project.id}
						className="flex flex-col gap-2 rounded-xl border border-brand-surface-border border-t-4 border-t-brand-primary bg-brand-surface p-5 text-inherit no-underline shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-lg"
					>
						<h3 className="m-0 text-base text-brand-primary-darker">{project.name}</h3>
						<p className="m-0 text-sm text-[#6b21a8]">{project.description || " "}</p>
					</Link>
				))}
				{projects.length === 0 && <p className="italic text-[#8b7aa8]">{t("projects.empty")}</p>}
			</div>
		</div>
	);
}

export default Projects;
