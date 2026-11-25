# -*- coding: utf-8 -*-
"""Axes 2D/3D.

Переключает оси (Grid) и уровни (Level) между режимами:
  * 2D / ViewSpecific — границы задаются отдельно в активном виде;
  * 3D / Model        — общие (модельные) границы для всех видов.

Если перед запуском выделить оси/уровни, обрабатываются только они.
Если выделения нет — все оси и уровни, видимые в активном виде.
"""

from pyrevit import revit, DB, forms, script

doc = revit.doc
uidoc = revit.uidoc
view = doc.ActiveView
output = script.get_output()

ENDS = (DB.DatumEnds.End0, DB.DatumEnds.End1)
MODEL = DB.DatumExtentType.Model
VIEW_SPECIFIC = DB.DatumExtentType.ViewSpecific

SUPPORTED_VIEW_TYPES = (
    DB.ViewType.FloorPlan,
    DB.ViewType.CeilingPlan,
    DB.ViewType.AreaPlan,
    DB.ViewType.EngineeringPlan,
    DB.ViewType.Section,
    DB.ViewType.Elevation,
)

OPT_TOGGLE = u"Переключить 2D \u2194 3D"
OPT_2D = u"Перевести в 2D (границы только в этом виде)"
OPT_3D = u"Перевести в 3D (общие границы модели)"


def datum_label(datum):
    try:
        return u"{} \u00ab{}\u00bb".format(datum.Category.Name, datum.Name)
    except Exception:
        return u"ID {}".format(datum.Id)


def current_ends(datum):
    """Возвращает режим обоих концов оси в активном виде."""
    modes = []
    for end in ENDS:
        try:
            modes.append(datum.GetDatumExtentTypeInView(end, view))
        except Exception:
            modes.append(None)
    return modes


def get_scope():
    """Выделенные оси/уровни или все видимые в активном виде."""
    selected = []
    for element_id in uidoc.Selection.GetElementIds():
        element = doc.GetElement(element_id)
        if isinstance(element, DB.DatumPlane):
            selected.append(element)

    if selected:
        return selected, u"выделенные элементы"

    collector = DB.FilteredElementCollector(doc, view.Id)
    grids = list(collector.OfClass(DB.Grid).WhereElementIsNotElementType())
    levels = list(collector.OfClass(DB.Level).WhereElementIsNotElementType())

    datums = {}
    for datum in grids + levels:
        datums[datum.Id.IntegerValue] = datum
    return list(datums.values()), u"все оси и уровни в активном виде"


def should_be_2d(datum, choice):
    if choice == OPT_2D:
        return True
    if choice == OPT_3D:
        return False

    modes = current_ends(datum)
    if any(mode is None for mode in modes):
        return True
    return all(mode == MODEL for mode in modes)


def apply_extents(datum, to_2d):
    if to_2d and not datum.CanBeVisibleInView(view):
        raise Exception(u"элемент не может отображаться в этом виде")

    target = VIEW_SPECIFIC if to_2d else MODEL
    for end in ENDS:
        datum.SetDatumExtentType(end, view, target)


def main():
    if view.ViewType not in SUPPORTED_VIEW_TYPES:
        forms.alert(
            u"Инструмент работает в планах, разрезах и фасадах.\n"
            u"Откройте такой вид и повторите запуск.",
            title=u"Оси 2D/3D"
        )
        script.exit()

    datums, scope = get_scope()
    if not datums:
        forms.alert(
            u"В активном виде не найдено осей или уровней.",
            title=u"Оси 2D/3D"
        )
        script.exit()

    choice = forms.CommandSwitchWindow.show(
        [OPT_TOGGLE, OPT_2D, OPT_3D],
        message=u"Режим для {} элементов ({})".format(len(datums), scope)
    )
    if not choice:
        script.exit()

    changed = 0
    errors = []
    total = len(datums)

    with forms.ProgressBar(title=u"Оси 2D/3D", cancellable=False) as progress:
        with revit.Transaction(u"Оси 2D/3D"):
            for index, datum in enumerate(datums):
                progress.update_progress(index, total)
                before = current_ends(datum)
                try:
                    apply_extents(datum, should_be_2d(datum, choice))
                    if current_ends(datum) != before:
                        changed += 1
                except Exception as ex:
                    errors.append(u"{}: {}".format(datum_label(datum), ex))
                progress.update_progress(index + 1, total)

    if errors:
        output.print_md(u"### Не удалось обработать")
        for error in errors:
            output.print_md(u"- {}".format(error))

    forms.alert(
        u"Всего: {}\nИзменено: {}\nНе удалось: {}\n\nОбласть: {}".format(
            total, changed, len(errors), scope
        ),
        title=u"Оси 2D/3D",
        warn_icon=bool(errors)
    )


if __name__ == "__main__":
    main()
