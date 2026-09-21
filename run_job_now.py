import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

# Import all models so SQLAlchemy mapper resolves every relationship
import app.features.users.users_models
import app.features.company.company_model
import app.features.sifarnici.country.country_model
import app.features.sifarnici.city.city_model
import app.features.sifarnici.exercise_option.exercise_option_model
import app.features.sifarnici.expense_category.expense_category_model
import app.features.sifarnici.income_category.income_category_model
import app.features.training.training_model
import app.features.training_users.training_users_model
import app.features.training_segments.training_segments_model
import app.features.season.season_model
import app.features.sifarnici.selection.selection_model
import app.features.season_selection_user.season_selection_user_model
import app.features.membership.membership_model
import app.features.contract.contract_model
import app.features.contract_installment.contract_installment_model
import app.features.tournament.tournament_model
import app.features.tournament_users.tournament_users_model
import app.features.wallet.wallet_model
import app.features.payment.payment_model

from app.scheduler.billing_jobs import run_nightly_billing_job
from app.scheduler.training_jobs import run_nightly_training_job

print("Running nightly training job now...")
run_nightly_training_job()
print("Running nightly billing job now...")
run_nightly_billing_job()
print("Done.")
