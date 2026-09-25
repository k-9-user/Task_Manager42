import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { isLoggedIn } from "../services/authService";

function NotFound()
{
	const { t } = useTranslation();

	return (
		<div className="flex min-h-full flex-col items-center justify-center gap-4 bg-brand-surface-alt p-8 text-center font-sans max-sm:p-4">
			<h1 className="m-0 text-brand-primary-darker">{t("notFound.title")}</h1>
			<p>{t("notFound.body")}</p>
			<Link
				to={isLoggedIn() ? "/projects" : "/login"}
				className="rounded-lg bg-brand-primary px-5 py-2.5 text-sm font-semibold text-white no-underline hover:bg-brand-primary-hover"
			>
				{t("notFound.back")}
			</Link>
		</div>
	);
}

export default NotFound;
