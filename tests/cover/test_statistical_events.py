# coding=utf-8
#
# This file is part of Hypothesis, which may be found at
# https://github.com/HypothesisWorks/hypothesis-python
#
# Most of this work is copyright (C) 2013-2017 David R. MacIver
# (david@drmaciver.com), but it contains contributions by others. See
# CONTRIBUTING.rst for a full list of people who may hold copyright, and
# consult the git log if you need to determine who owns an individual
# contribution.
#
# This Source Code Form is subject to the terms of the Mozilla Public License,
# v. 2.0. If a copy of the MPL was not distributed with this file, You can
# obtain one at http://mozilla.org/MPL/2.0/.
#
# END HEADER

from __future__ import division, print_function, absolute_import

import re
import time
import traceback

import pytest

from hypothesis import strategies as st
from hypothesis import HealthCheck, event, given, example, settings
from hypothesis.statistics import collector


def call_for_statistics(test_function):
    result = [None]

    def callback(statistics):
        result[0] = statistics

    with collector.with_value(callback):
        try:
            test_function()
        except Exception:
            traceback.print_exc()
    assert result[0] is not None
    return result[0]


def test_can_callback_with_a_string():
    @given(st.integers())
    def test(i):
        event('hi')

    stats = call_for_statistics(test)

    assert any('hi' in s for s in stats.events)


counter = 0
seen = []


class Foo(object):

    def __eq__(self, other):
        return True

    def __ne__(self, other):
        return False

    def __hash__(self):
        return 0

    def __str__(self):
        seen.append(self)
        global counter
        counter += 1
        return 'COUNTER %d' % (counter,)


def test_formats_are_evaluated_only_once():
    global counter
    counter = 0

    @given(st.integers())
    def test(i):
        event(Foo())

    stats = call_for_statistics(test)

    assert any('COUNTER 1' in s for s in stats.events)
    assert not any('COUNTER 2' in s for s in stats.events)


def test_does_not_report_on_examples():
    @example('hi')
    @given(st.integers())
    def test(i):
        if isinstance(i, str):
            event('boo')

    stats = call_for_statistics(test)
    assert not any('boo' in e for e in stats.events)


def test_exact_timing():
    @settings(suppress_health_check=[HealthCheck.too_slow], deadline=None)
    @given(st.integers())
    def test(i):
        time.sleep(0.5)

    stats = call_for_statistics(test)
    assert re.match(r'~ 5\d\dms', stats.runtimes)


def test_apparently_instantaneous_tests():
    time.freeze()

    @given(st.integers())
    def test(i):
        pass

    stats = call_for_statistics(test)
    assert stats.runtimes == '< 1ms'


def test_flaky_exit():
    first = [True]

    @given(st.integers())
    def test(i):
        if i > 1001:
            if first[0]:
                first[0] = False
                print('Hi')
                assert False

    stats = call_for_statistics(test)
    assert stats.exit_reason == 'test was flaky'


@pytest.mark.parametrize('draw_delay', [False, True])
@pytest.mark.parametrize('test_delay', [False, True])
def test_draw_time_percentage(draw_delay, test_delay):
    time.freeze()

    @st.composite
    def s(draw):
        if draw_delay:
            time.sleep(0.05)

    @given(s())
    def test(_):
        if test_delay:
            time.sleep(0.05)

    stats = call_for_statistics(test)
    if not draw_delay:
        assert stats.draw_time_percentage == '~ 0%'
    elif test_delay:
        assert stats.draw_time_percentage == '~ 50%'
    else:
        assert stats.draw_time_percentage == '~ 100%'


def test_has_lambdas_in_output():
    @given(st.integers().filter(lambda x: x % 2 == 0))
    def test(i):
        pass

    stats = call_for_statistics(test)
    print(stats.events)
    assert any(
        'lambda x: x % 2 == 0' in e for e in stats.events
    )
