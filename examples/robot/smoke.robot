*** Settings ***
Documentation     What every suite can count on the action having set up.
...               The pytest version of this lives in examples/pytest.
Library           OperatingSystem

*** Test Cases ***
The output directory exists and is ours
    ${outdir}=    Get Environment Variable    MOONFORGE_TEST_OUTDIR
    Directory Should Exist    ${outdir}
    Create File    ${outdir}/smoke.txt    the suite wrote this\n

The suite runs from workdir
    ${workdir}=    Get Environment Variable    MOONFORGE_TEST_WORKDIR
    ${cwd}=    Evaluate    os.getcwd()    os
    Should Be Equal    ${cwd}    ${workdir}
