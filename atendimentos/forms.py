from django import forms
from django.utils import timezone


RISCOS = {
    1: "1 Emergência",
    2: "2 Muito urgente",
    3: "3 Urgente",
    4: "4 Pouco urgente",
    5: "5 Não urgente",
}


class BuscaForm(forms.Form):
    id = forms.IntegerField(label="ID", min_value=1)


class PacienteForm(forms.Form):
    nome = forms.CharField(label="Nome do paciente", max_length=150)
    chegada = forms.DateTimeField(
        label="Chegada (horário de Brasília)",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
    )
    prioridade = forms.TypedChoiceField(label="Classificação de risco", choices=RISCOS.items(), coerce=int)

    def clean_chegada(self):
        chegada = self.cleaned_data["chegada"]
        if chegada > timezone.now():
            raise forms.ValidationError("A chegada não pode estar no futuro.")
        return chegada


class ReclassificacaoForm(BuscaForm):
    prioridade = forms.TypedChoiceField(label="Nova classificação", choices=RISCOS.items(), coerce=int)


class MedicoForm(forms.Form):
    nome = forms.CharField(label="Nome do médico", max_length=150)
    registro = forms.CharField(label="Registro profissional fictício", max_length=40)
