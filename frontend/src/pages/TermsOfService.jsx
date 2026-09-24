import { useTranslation } from 'react-i18next';
import './Legal.css';

function TermsOfService ()
{
	const { t } = useTranslation();

	return (
		<div className="legal-page">
			<h1>{t("legal.terms.title")}</h1>
			<p><em>{t("legal.updated")}</em></p>
			<h2>{t("legal.terms.section1Title")}</h2>
			<p>{t("legal.terms.section1Body")}</p>
			<h2>{t("legal.terms.section2Title")}</h2>
			<p>{t("legal.terms.section2Body")}</p>
			<h2>{t("legal.terms.section3Title")}</h2>
			<p>{t("legal.terms.section3Body")}</p>
		</div>
	);
}

export default TermsOfService;
