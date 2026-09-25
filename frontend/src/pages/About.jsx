import { useTranslation } from 'react-i18next';
import './Legal.css';

const FEATURES = ["projects", "tasks", "discussion", "search", "gamification", "api", "privacy", "languages"];
const LIMITS = ["local", "certificate", "google", "email", "refresh", "api", "reset"];

function About ()
{
	const { t } = useTranslation();

	return (
		<div className="legal-page">
			<h1>{t("about.title")}</h1>
			<p>{t("about.intro")}</p>
			<h2>{t("about.featuresTitle")}</h2>
			<ul className="legal-rights">
				{FEATURES.map((feature) => (
					<li key={feature}>{t(`about.features.${feature}`)}</li>
				))}
			</ul>
			<h2>{t("about.stackTitle")}</h2>
			<p>{t("about.stackBody")}</p>
			<h2>{t("about.limitsTitle")}</h2>
			<ul className="legal-rights">
				{LIMITS.map((limit) => (
					<li key={limit}>{t(`about.limits.${limit}`)}</li>
				))}
			</ul>
		</div>
	);
}

export default About;
