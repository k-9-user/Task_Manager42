import { Fragment } from 'react';
import { useTranslation } from 'react-i18next';
import './Legal.css';

const SECTIONS = ["purpose", "account", "use", "content", "api", "moderation", "liability", "changes"];

function TermsOfService ()
{
	const { t } = useTranslation();

	return (
		<div className="legal-page">
			<h1>{t("legal.terms.title")}</h1>
			<p><em>{t("legal.updated")}</em></p>
			{SECTIONS.map((section) => (
				<Fragment key={section}>
					<h2>{t(`legal.terms.sections.${section}.title`)}</h2>
					<p>{t(`legal.terms.sections.${section}.body`)}</p>
				</Fragment>
			))}
		</div>
	);
}

export default TermsOfService;
