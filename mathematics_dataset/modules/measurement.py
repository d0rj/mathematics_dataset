# -*- coding: utf-8 -*-
# Copyright 2018 DeepMind Technologies Limited.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Measurement questions, e.g., "How many hours are there in a day?"."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import collections
import functools
import random

# Dependency imports
from mathematics_dataset import example
from mathematics_dataset.modules import train_test_split
from mathematics_dataset.sample import number
from mathematics_dataset.util import composition
from mathematics_dataset.util import display
import six
import sympy


def _make_modules(is_train):
  """Returns modules, with split based on the boolean `is_train`."""
  return {
      'conversion': functools.partial(
          conversion, is_train=is_train, is_extrapolation=False),
      'time': functools.partial(time, is_train=is_train),
  }


def train(entropy_fn):
  """Returns dict of training modules."""
  del entropy_fn  # unused
  return _make_modules(is_train=True)


def test():
  """Returns dict of testing modules."""
  return _make_modules(is_train=False)


def test_extra():
  """Returns dict of extrapolation testing modules."""
  return {
      'conversion': functools.partial(
          conversion, is_train=False, is_extrapolation=True),
  }


Unit = collections.namedtuple('Unit', ('name', 'symbol'))


MICRO_SYMBOL = 'u'


LENGTH = {
    Unit('метр', 'm'): 1,
    Unit('километр', 'km'): 1000,
    Unit('сантиметр', 'cm'): sympy.Rational(1, 100),
    Unit('миллиметр', 'mm'): sympy.Rational(1, 1000),
    Unit('микрометр', 'um'): sympy.Rational(1, 1e6),
    Unit('нанометр', 'nm'): sympy.Rational(1, 1e9),
}

TIME = {
    Unit('секунда', 's'): 1,
    Unit('минута', None): 60,
    Unit('час', None): 60*60,
    Unit('день', None): 24*60*60,
    Unit('неделя', None): 7*24*60*60,
    Unit('миллисекунда', 'ms'): sympy.Rational(1, 1e3),
    Unit('микросекунда', MICRO_SYMBOL + 's'): sympy.Rational(1, 1e6),
    Unit('наносекунда', 'ns'): sympy.Rational(1, 1e9),
}

TIME_YEARLY = {
    Unit('год', None): 1,
    Unit('десятилетие', None): 10,
    Unit('век', None): 100,
    Unit('тысячелетие', None): 1000,
    Unit('месяц', None): sympy.Rational(1, 12),
}

MASS = {
    Unit('килограмм', 'kg'): 1,  # Yes, the *kilo*gram is the SI base unit.
    Unit('тонна', 't'): 1000,
    Unit('грамм', 'g'): sympy.Rational(1, 1e3),
    Unit('миллиграмм', 'mg'): sympy.Rational(1, 1e6),
    Unit('микрограмм', MICRO_SYMBOL + 'g'): sympy.Rational(1, 1e9),
    Unit('нанограмм', 'ng'): sympy.Rational(1, 1e12),
}

VOLUME = {
    Unit('литр', 'l'): 1,
    Unit('миллилитр', 'ml'): sympy.Rational(1, 1000),
}


DIMENSIONS = [LENGTH, TIME, TIME_YEARLY, MASS, VOLUME]


def pluralize(name):
  # Russian genitive plural forms for units.
  irregular = {
      'метр': 'метров',
      'километр': 'километров',
      'сантиметр': 'сантиметров',
      'миллиметр': 'миллиметров',
      'микрометр': 'микрометров',
      'нанометр': 'нанометров',
      'секунда': 'секунд',
      'минута': 'минут',
      'час': 'часов',
      'день': 'дней',
      'неделя': 'недель',
      'миллисекунда': 'миллисекунд',
      'микросекунда': 'микросекунд',
      'наносекунда': 'наносекунд',
      'год': 'лет',
      'десятилетие': 'десятилетий',
      'век': 'веков',
      'тысячелетие': 'тысячелетий',
      'месяц': 'месяцев',
      'килограмм': 'килограммов',
      'тонна': 'тонн',
      'грамм': 'граммов',
      'миллиграмм': 'миллиграммов',
      'микрограмм': 'микрограммов',
      'нанограмм': 'нанограммов',
      'литр': 'литров',
      'миллилитр': 'миллилитров',
  }
  return irregular.get(name, name)


def genitive_singular(name):
  # Russian genitive singular forms for units ("килограмм" -> "килограмма").
  irregular = {
      'метр': 'метра',
      'километр': 'километра',
      'сантиметр': 'сантиметра',
      'миллиметр': 'миллиметра',
      'микрометр': 'микрометра',
      'нанометр': 'нанометра',
      'секунда': 'секунды',
      'минута': 'минуты',
      'час': 'часа',
      'день': 'дня',
      'неделя': 'недели',
      'миллисекунда': 'миллисекунды',
      'микросекунда': 'микросекунды',
      'наносекунда': 'наносекунды',
      'год': 'года',
      'десятилетие': 'десятилетия',
      'век': 'века',
      'тысячелетие': 'тысячелетия',
      'месяц': 'месяца',
      'килограмм': 'килограмма',
      'тонна': 'тонны',
      'грамм': 'грамма',
      'миллиграмм': 'миллиграмма',
      'микрограмм': 'микрограмма',
      'нанограмм': 'нанограмма',
      'литр': 'литра',
      'миллилитр': 'миллилитра',
  }
  return irregular.get(name, name)


def accusative_singular(name):
  # Russian accusative singular forms for units ("тонна" -> "тонну").
  irregular = {
      'метр': 'метр',
      'километр': 'километр',
      'сантиметр': 'сантиметр',
      'миллиметр': 'миллиметр',
      'микрометр': 'микрометр',
      'нанометр': 'нанометр',
      'секунда': 'секунду',
      'минута': 'минуту',
      'час': 'час',
      'день': 'день',
      'неделя': 'неделю',
      'миллисекунда': 'миллисекунду',
      'микросекунда': 'микросекунду',
      'наносекунда': 'наносекунду',
      'год': 'год',
      'десятилетие': 'десятилетие',
      'век': 'век',
      'тысячелетие': 'тысячелетие',
      'месяц': 'месяц',
      'килограмм': 'килограмм',
      'тонна': 'тонну',
      'грамм': 'грамм',
      'миллиграмм': 'миллиграмм',
      'микрограмм': 'микрограмм',
      'нанограмм': 'нанограмм',
      'литр': 'литр',
      'миллилитр': 'миллилитр',
  }
  return irregular.get(name, name)


def nominative_plural(name):
  # Russian nominative plural forms for units (used as accusative for inanimate).
  irregular = {
      'метр': 'метры',
      'километр': 'километры',
      'сантиметр': 'сантиметры',
      'миллиметр': 'миллиметры',
      'микрометр': 'микрометры',
      'нанометр': 'нанометры',
      'секунда': 'секунды',
      'минута': 'минуты',
      'час': 'часы',
      'день': 'дни',
      'неделя': 'недели',
      'миллисекунда': 'миллисекунды',
      'микросекунда': 'микросекунды',
      'наносекунда': 'наносекунды',
      'год': 'годы',
      'десятилетие': 'десятилетия',
      'век': 'веки',
      'тысячелетие': 'тысячелетия',
      'месяц': 'месяцы',
      'килограмм': 'килограммы',
      'тонна': 'тонны',
      'грамм': 'граммы',
      'миллиграмм': 'миллиграммы',
      'микрограмм': 'микрограммы',
      'нанограмм': 'нанограммы',
      'литр': 'литры',
      'миллилитр': 'миллилитры',
  }
  return irregular.get(name, name)


def _unit_form_for_number(name, value):
  """Returns the unit form that follows a numeric value.

  E.g. 1 -> "метр", 2-4 -> "метра", 5+ -> "метров"; non-integers use the
  genitive singular ("2.5 метра").
  """
  if isinstance(value, display.Decimal):
    number_value = float(value.value)
  else:
    number_value = float(value)
  if number_value == int(number_value):
    number_value = int(number_value)
    if number_value == 1:
      return name
    elif 2 <= number_value <= 4:
      return genitive_singular(name)
    else:
      return pluralize(name)
  else:
    return genitive_singular(name)


def prepositional_plural(name):
  # Russian prepositional plural forms for units ("метр" -> "метрах").
  irregular = {
      'метр': 'метрах',
      'километр': 'километрах',
      'сантиметр': 'сантиметрах',
      'миллиметр': 'миллиметрах',
      'микрометр': 'микрометрах',
      'нанометр': 'нанометрах',
      'секунда': 'секундах',
      'минута': 'минутах',
      'час': 'часах',
      'день': 'днях',
      'неделя': 'неделях',
      'миллисекунда': 'миллисекундах',
      'микросекунда': 'микросекундах',
      'наносекунда': 'наносекундах',
      'год': 'годах',
      'десятилетие': 'десятилетиях',
      'век': 'веках',
      'тысячелетие': 'тысячелетиях',
      'месяц': 'месяцах',
      'килограмм': 'килограммах',
      'тонна': 'тоннах',
      'грамм': 'граммах',
      'миллиграмм': 'миллиграммах',
      'микрограмм': 'микрограммах',
      'нанограмм': 'нанограммах',
      'литр': 'литрах',
      'миллилитр': 'миллилитрах',
  }
  return irregular.get(name, name)


def _factor_non_decimal(value):
  """Extras x dividing value such that x is coprime to 2 and 5."""
  result = 1
  factors = sympy.factorint(value)
  for factor, power in six.iteritems(factors):
    if factor not in [2, 5]:
      result *= factor ** power
  return result


def _sample_conversion_decimal(dimension, is_extrapolation):
  """Samples to and from units and values."""
  base_unit, target_unit = random.sample(list(dimension.keys()), 2)
  scale = sympy.Rational(dimension[base_unit]) / dimension[target_unit]
  scale_non_decimal = _factor_non_decimal(sympy.denom(scale))
  entropy = 9 if is_extrapolation else 7
  base_value = number.non_integer_decimal(entropy, signed=False)
  base_value = display.Decimal(base_value.value * scale_non_decimal)
  target_value = display.Decimal(base_value.value * scale)
  return base_value, base_unit, target_value, target_unit


def _conversion_decimal(context, is_train, is_extrapolation):
  """E.g., "How many grams are in 5kg?"."""
  dimension = random.choice(DIMENSIONS)
  while True:
    base_value, base_unit, target_value, target_unit = (
        _sample_conversion_decimal(dimension, is_extrapolation))
    if train_test_split.is_train(base_value) == is_train:
      break

  base_form = _unit_form_for_number(base_unit.name, base_value)
  base_prep = prepositional_plural(base_unit.name)
  target_gen = pluralize(target_unit.name)
  target_prep = prepositional_plural(target_unit.name)
  target_nom = nominative_plural(target_unit.name)

  templates = [
      'Сколько {target_gen} в {base_value} {base_prep}?',
      'Сколько {base_value} {base_form} в {target_prep}?',
      'Переведите {base_value} {base_form} в {target_nom}.',
  ]
  template = random.choice(templates)

  question = example.question(
      context,
      template,
      base_value=base_value,
      base_form=base_form,
      base_prep=base_prep,
      target_gen=target_gen,
      target_prep=target_prep,
      target_nom=target_nom)
  return example.Problem(question=question, answer=target_value)


def _conversion_fraction(context, is_train):
  """E.g., "How many grams are in three quarters of a kg?"."""
  dimension = random.choice(DIMENSIONS)

  # Limit probability of giving zero answer.
  allow_zero = random.random() < 0.2

  # Repeat until we find a pair with an integral answer. (Avoids ambiguity with
  # decimals.)
  while True:
    base_unit, target_unit = random.sample(list(dimension.keys()), 2)
    base_value = number.non_integer_rational(2, signed=False)
    if train_test_split.is_train(base_value) != is_train:
      continue
    answer = (base_value * sympy.Rational(dimension[base_unit])
              / sympy.Rational(dimension[target_unit]))
    if (abs(answer) <= 100000
        and sympy.denom(answer) == 1
        and (allow_zero or answer != 0)):
      break

  template = random.choice([
      'Сколько {base_value} {base_name} в {target_prep}?',
  ])

  base_value_string = base_value  # e.g., 2/3

  question = example.question(
      context, template,
      base_name=genitive_singular(base_unit.name),
      base_value=base_value_string,
      target_prep=prepositional_plural(target_unit.name))
  return example.Problem(question=question, answer=answer)


def conversion(is_train, is_extrapolation):
  """Conversion question, in decimal or fraction."""
  context = composition.Context()
  # TODO(b/124038528): implement extrapolation for fraction conversions too
  if is_extrapolation or random.choice([False, True]):
    return _conversion_decimal(
        context, is_train=is_train, is_extrapolation=is_extrapolation)
  else:
    return _conversion_fraction(context, is_train=is_train)


def time(is_train):
  """Questions for calculating start, end, or time differences."""
  context = composition.Context()
  start_minutes = random.randint(1, 24*60 - 1)
  while True:
    duration_minutes = random.randint(1, 12*60 - 1)
    if train_test_split.is_train(duration_minutes) == is_train:
      break
  end_minutes = start_minutes + duration_minutes

  def format_12hr(minutes):
    """Format minutes from midnight in 12 hr format."""
    hours = (minutes // 60) % 24
    minutes %= 60
    am_pm = 'утра' if hours < 12 else 'вечера'
    hours = (hours - 1) % 12 + 1
    return '{}:{:02} {}'.format(hours, minutes, am_pm)

  start = format_12hr(start_minutes)
  end = format_12hr(end_minutes)

  which_question = random.randint(0, 3)
  if which_question == 0:
    # Question: What is start = end - duration?
    template = random.choice([
        'Который час будет за {duration} минут до {end}?',
    ])
    return example.Problem(
        question=example.question(
            context, template, duration=duration_minutes, end=end),
        answer=start)
  elif which_question == 1:
    # Question: What is end = start + duration?
    template = random.choice([
        'Который час будет через {duration} минут после {start}?',
    ])
    return example.Problem(
        question=example.question(
            context, template, duration=duration_minutes, start=start),
        answer=end)
  else:
    # Question: What is duration = end - start?
    template = random.choice([
        'Сколько минут между {start} и {end}?',
    ])
    return example.Problem(
        question=example.question(context, template, start=start, end=end),
        answer=duration_minutes)
