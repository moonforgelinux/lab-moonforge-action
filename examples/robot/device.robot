*** Settings ***
Documentation     Checks against the device the action reserved and
...               flashed.
...
...               Skipped when there is none, so the same suite runs on
...               the runner and in the lab. Logging in uses the empty
...               root password a Moonforge image built with
...               kas/common/debug.yml leaves; without that fragment
...               there is no SSH server at all.
...
...               The pytest version of this lives in examples/pytest.
Library           OperatingSystem
Library           SSHLibrary
Suite Setup       Log In To The Device
Suite Teardown    Close All Connections

*** Keywords ***
Log In To The Device
    ${ip}=    Get Environment Variable    DUT_IP    ${EMPTY}
    Skip If    $ip == ''    no device; set dut_pool to run these
    ${port}=    Get Environment Variable    DUT_SSH_PORT    22
    Open Connection    ${ip}    port=${port}    timeout=60s
    # The password is empty, not absent. Clear SSH_AUTH_SOCK so set allow_agent
    # to bypass SSHLibrary's broken path.
    Remove Environment Variable    SSH_AUTH_SOCK
    Login    root    ${EMPTY}    allow_agent=${True}

On Device
    [Documentation]    Run a command on the device and return what it
    ...                printed.
    [Arguments]    ${command}
    ${out}    ${rc}=    Execute Command    ${command}    return_rc=${True}
    Should Be Equal As Integers    ${rc}    0
    RETURN    ${out.strip()}

*** Test Cases ***
The device runs the image that was flashed
    ${id}=    On Device    . /etc/os-release && echo $ID
    Should Be Equal    ${id}    moonforge

The root filesystem is read only
    [Documentation]    Moonforge is immutable; a writable root means the
    ...                wrong image.
    ${options}=    On Device    findmnt -no OPTIONS /
    Should Contain    ${options.split(',')}    ro

Data is a writable overlay
    [Documentation]    Everything that has to survive a reboot lives
    ...                there.
    On Device    echo written > /data/lab-moonforge-action.check
    ${content}=    On Device    cat /data/lab-moonforge-action.check
    Should Be Equal    ${content}    written
