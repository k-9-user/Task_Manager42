import { useRef, useState, useEffect } from "react";
import { getProjects, createProject } from "../services/projectService";
import { MAX_IMPORT_SIZE_MB, exportData, importAcceptAttr, importData, validateImportFile } from "../services/dataService";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

const CREATE_BUTTON = "cursor-pointer rounded-lg border-none bg-brand-primary px-5 py-2.5 text-sm font-semibold text-white hover:bg-brand-primary-hover";
const DATA_BUTTON = "cursor-pointer rounded-md border border-brand-surface-border bg-brand-surface px-4 py-2 text-sm font-semibold text-brand-primary-darker hover:bg-brand-surface-alt disabled:cursor-not-allowed disabled:opacity-60";

function Projects()
{
	const [projects, setProjects] = useState([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState("");
	const [name, setName] = useState("");
	const [description, setDescription] = useState("");
	const [showForm, setShowForm] = useState(false);
	const [showData, setShowData] = useState(false);
	const [importing, setImporting] = useState(false);
	const [notice, setNotice] = useState("");
	const importInputRef = useRef(null);
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

	async function handleExport(format)
	{
		setError("");
		setNotice("");
		try
		{
			await exportData(format);
		}
		catch (err)
		{
			setError(err.message);
		}
	}

	async function handleImport(e)
	{
		const file = e.target.files?.[0];

		e.target.value = "";
		if (!file)
			return;

		const invalid = validateImportFile(file);

		if (invalid)
		{
			setNotice("");
			setError(t(invalid, { max: MAX_IMPORT_SIZE_MB }));
			return;
		}
		setImporting(true);
		setError("");
		setNotice("");
		try
		{
			const data = await importData(file);
			const messages = [t("data.imported", { count: data.imported_count })];

			if (data.created_projects)
				messages.push(t("data.createdProjects", { count: data.created_projects }));
			setNotice(messages.join(" · "));
			setProjects((await getProjects()).projects);
		}
		catch (err)
		{
			setError(err.message);
		}
		finally
		{
			setImporting(false);
		}
	}

	if (loading)
		return <p>{t("loading.load")}</p>;

	const isEmpty = projects.length === 0 && !showForm;

	return (
		<div className="flex min-h-full flex-1 flex-col gap-6 bg-brand-surface-alt p-8 font-sans max-sm:p-4">
			<div className="flex flex-wrap items-center justify-between gap-4">
				<h1 className="m-0 text-brand-primary-darker">{t("projects.title")}</h1>
				<div className="flex flex-wrap items-center gap-2.5">
					<button className={DATA_BUTTON} onClick={() => setShowData(!showData)}>
						{t("data.title")}
					</button>
					{!isEmpty && (
						<button className={CREATE_BUTTON} onClick={() => setShowForm(!showForm)}>
							{showForm ? t("register.return") : `+ ${t("projects.create")}`}
						</button>
					)}
				</div>
			</div>
			{error && <p className="m-0 rounded-lg bg-red-100 px-3 py-2 text-sm text-red-700">{error}</p>}
			{notice && <p className="m-0 rounded-lg bg-green-100 px-3 py-2 text-sm text-green-800" role="status">{notice}</p>}
			{showData && (
				<section className="flex flex-col gap-3 rounded-xl border border-brand-surface-border bg-brand-surface p-4">
					<div className="flex flex-wrap items-center gap-2.5">
						<span className="text-sm font-semibold text-brand-primary-darker">{t("data.export")}</span>
						<button className={DATA_BUTTON} onClick={() => handleExport("json")}>JSON</button>
						<button className={DATA_BUTTON} onClick={() => handleExport("csv")}>CSV</button>
					</div>
					<div className="flex flex-wrap items-center gap-2.5">
						<span className="text-sm font-semibold text-brand-primary-darker">{t("data.import")}</span>
						<input
							ref={importInputRef}
							type="file"
							accept={importAcceptAttr()}
							onChange={handleImport}
							hidden
						/>
						<button
							type="button"
							className={DATA_BUTTON}
							disabled={importing}
							onClick={() => importInputRef.current?.click()}
						>
							{t("data.pick")}
						</button>
						{importing && <span className="text-sm text-[#6b21a8]">{t("data.importing")}</span>}
					</div>
					<p className="m-0 text-sm text-[#6b21a8]">{t("data.hint", { max: MAX_IMPORT_SIZE_MB })}</p>
				</section>
			)}
			{showForm && (
				<form onSubmit={handleCreate} className="flex flex-wrap gap-2.5 rounded-xl border border-brand-surface-border bg-brand-surface p-4">
					<input
						type="text"
						placeholder={t("projects.namePlaceholder")}
						aria-label={t("projects.namePlaceholder")}
						maxLength={255}
						value={name}
						onChange={(e) => setName(e.target.value)}
						className="min-w-40 flex-1 rounded-md border border-brand-surface-border px-2.5 py-2 text-sm"
					/>
					<input
						type="text"
						placeholder={t("projects.description")}
						aria-label={t("projects.description")}
						maxLength={5000}
						value={description}
						onChange={(e) => setDescription(e.target.value)}
						className="min-w-40 flex-1 rounded-md border border-brand-surface-border px-2.5 py-2 text-sm"
					/>
					<button type="submit" className="cursor-pointer rounded-md border-none bg-brand-primary px-4 py-2 text-sm font-semibold text-white hover:bg-brand-primary-hover">
						{t("projects.create")}
					</button>
				</form>
			)}
			{isEmpty ? (
				<div className="flex flex-1 flex-col items-center justify-center gap-4 text-center">
					<p className="m-0 text-lg italic text-[#8b7aa8]">{t("projects.empty")}</p>
					<button className={CREATE_BUTTON} onClick={() => setShowForm(true)}>
						+ {t("projects.create")}
					</button>
				</div>
			) : (
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
				</div>
			)}
		</div>
	);
}

export default Projects;
