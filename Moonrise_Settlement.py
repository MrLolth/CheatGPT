"""
Submission for HackPHS 2026
"Moonrise Settlement"
Leo Schwarz, Adam Schwarz, Jeffrey Huang, Divyesh Purohit
10/11/2026
"""

import random
import threading
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
app.secret_key = 'moonrise_secret_colony_key'

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/game")
def game():
    return render_template(
        "settlements.html",
        pop=pop,
        res=res,
        fund=fund,
        rel=rel,
    )


@app.route("/api/stats")
def stats():
    return jsonify(population=pop, resources=res, funding=fund, relations=rel)

@app.route("/api/state")
def game_state():
    with game_lock:
        ensure_current_event()
        return jsonify(state_payload())

@app.route("/api/action", methods=["POST"])
def submit_action():
    global current_event, upcoming_events, game_turn, game_over, game_message, last_result
    global pop, res, fund, rel  # Explicitly pull in the global stat tracking variables

    payload = request.get_json()
    answer = payload.get("answer") if isinstance(payload, dict) else None
    if answer not in ("yes", "no"):
        return jsonify(error="Answer must be 'yes' or 'no'."), 400

    with game_lock:
        if game_over:
            return jsonify(error="The game is over.", **state_payload()), 409

        # 1. Sync engine dictionary with your live global variables before running the turn
        all_stats["Population"] = pop
        all_stats["Resources"] = res
        all_stats["Funding"] = fund
        all_stats["Relations"] = rel

        ensure_current_event()
        dependent_event, upcoming_events, last_result = do_turn(
            all_stats,
            upcoming_events,
            answer=answer,
            event=current_event,
        )
        current_event = None

        # Keep the shared stats dictionary in sync with the values do_turn updated.
        all_stats.update({
            "Population": pop,
            "Resources": res,
            "Funding": fund,
            "Relations": rel,
            "You": u,
        })

        if dependent_event:
            events_running[dependent_event] = events[dependent_event]

        next_event = upcoming_events[0] if upcoming_events else None
        if next_event in list_of_dependent_event:
            events_running.pop(next_event, None)

        game_turn += 1
        game_over, game_message = get_game_result(game_turn)
        ensure_current_event()
        return jsonify(state_payload(result=last_result))

@app.route("/api/reset", methods=["POST"])
def reset_game():
    global pop, res, fund, rel, u, run, upcoming_events, all_stats
    global events_running, current_event, game_turn, game_over, game_message, last_result

    with game_lock:
        pop, res, fund, rel, u = 50.0, 50.0, 50.0, 50.0, 1
        passive_prfr_regen[:] = [0, 0, 0, 0]
        run = True
        events_running = events_running_initial()
        upcoming_events = random.sample(list(events_running), min(5, len(events_running)))
        current_event = None
        game_turn = 1
        game_over = False
        game_message = ""
        last_result = ""
        all_stats = {
            "Population": pop,
            "Resources": res,
            "Funding": fund,
            "Relations": rel,
            "You": u,
        }
        ensure_current_event()
        return jsonify(state_payload())

# setup variables
pop = 50.0 # population
res = 50.0 # resources (out of 100)
fund = 50.0 # funding (in millions of dollars)
rel = 50.0 # relations with other colonists (out of 100)
u = 1 # lives
passive_prfr_regen = [0, 0, 0, 0] # passive pop, res, fund and rel generation per turn


run = True # keep running the game?
upcoming_events = [] # list of events that will happen in the next 5 turns


all_stats = {"Population": pop, "Resources": res, "Funding": fund, "Relations": rel, "You": 1} # list of all stats in order


    # dictionary of all the possible events
events = {
    # format: "name": [text, [yes],[no]]
    # yes/no format: [possibility, possibility, etc]
    # format for possibilities: [text, stat changes, chance, event (if any)]
    # can leave event empty

        "Eat and Breathe": ["Your crew needs to eat. ",
            [["Your crew uses some resources to eat. ", {"res": -10}, 1]],
            [["Some of your crew dies from starvation. ", {"pop": -10, "rel": -10}, 1]]],
       
        "Alien Encounter S": ["You spot a small alien spaceship flying by, do you try to attack it? ",
            [["You attacked it and won! ", {"res": 10, }, 0.7], ["Your attack failed. ", {"pop": -3, "res": -5}, 0.3]],
            [["They passed by. ", {"": 0}, 0.8], ["They attacked you! ", {"res": -10,"pop": -5}, 0.2]]],

        "Alien Encounter L": ["You spot a large alien spaceship flying by, do you try to attack it? ",
            [["You attacked it and won! ", {"res": 25}, 0.2], ["Your attack failed. ", {"pop": -7, "res": -10}, 0.8]],
            [["They passed by. ", {"": 0}, 0.3], ["They attacked you! ", {"res": -20,"pop": -10}, 0.7]]],
       
        "Mutiny": ["There is an attempted mutiny in the colony, do you shut it down with force? ",
            [["You succesfully shut it down. ", {"pop": -10, "rel": -10, "res": 10}, 0.7], ["You failed to shut it down and some of the colonists left to form a new colony. ", {"pop":-20, "res": -20}, 0.3]],
            [["You ignore the mutiny and get overthrown! ", {"you": -1}, 1.0]]],
       
        "Research proposal": ["A scientist approaches you with the proposal to find eternal life in exchange for $40 million! Do you accept? ",
            [["The scientist disapears into thin air with your funds. ", {"fund": -40, "pop": -1}, 1.0, "Eternal_Result"]],
            [["You decline and the scientist disappears. ", {"pop": -1}, 1.0]]],

        "Eternal_Result": ["The scientist is back! Do you let them in? ",
            [["The scientist found nothing.", {"pop":1}, 0.9], ["The scientist found a way to grant you an extra life!!!", {"u":1, "pop":1}, 0.1]],
            [["You refuse to let the scientist return", {"": 0}, 1.0]]],        

        "Bye": ["Some of your crew asks to leave the colony, do you let them go? ",
            [["Some of your crew left. ", {"pop": -5, "rel": 5},1,"Hi"]],
            [["You refuse to let them leave. ",{"rel": -10},1,"Bye"]]],

        "Hi": ["New people arrived, do you take them in? ",
            [["You welcomed them to your crew. ",{"pop":+5, "res": -5},1]],
            [["You refused to let them enter. ",{"": 0},1]]],
       
        "Request Funding": ["Would you like to request more funding? ",
            [["Your request was granted! ", {"fund": 10}, 0.6], ["Your request was partially granted. ", {"fund": 5}, 0.2], ["Your request was denied! ", {"rel": -5}, 0.2]],
            [["You didn't request funding. ", {"": 0}, 1]]],

        "Solar Panels": ["The government asks you if you want to install solar panels. ",
            [["You agreed to add solar panels, and you now get 0.25 more resources per turn! ",{"fund":-15, "res": -10, "res_regen": 0.25},1]],
            [["You refused to install solar panels. ",{"rel": -5},1]]],

        "Exploration": ["A group of your crew propose an expedition to explore a different area on the moon, do you agree? ",
            [["You agreed to the expedition and the group left, ", {"pop":-10,"res":-5, "rel": 5},1,"Exploration_Result"]],
            [["You refused the expedition. ", {"rel":-3},1]]],

        "Exploration_Result": ["The expedition returned, do you take the crew back in? ",
            [["The expedition was a success! ", {"res":+20,"pop":10},0.2],["The expedition crew found nothing. ", {"pop":10}, 0.7],["The expedition ended in disaster! Only 2 crew members made it back. ", {"pop":2},0.1]],
            [["The expedition crew leaves. ", {"":0},1]]],

        "Foreigners": ["A group of foreigners arrived to the colony. They claim to be running low on resources. Do you help them? ",
            [["You helped the foreigners. ", {"res":-5, "rel": 3},1]],
            [["You refused to help the foreigners", {"rel":-3},1]]],

        "Meteor Shower": ["A meteor shower is approaching the colony, do you take precautions? ",
            [["You took precautions and minimized damage. ", {"res":-5},1]],
            [["You ignored the meteor shower and suffered damage! ", {"res":-10,"pop":-1},0.5], ["The meteor shower missed the colony. ", {"": 0}, 0.5]]],

        "New Settlement": ["A group of your crew wants to establish a new settlement nearby, do you agree? ",
            [["You agreed to the new settlement. It will provide you with 0.1 extra resources per turn! ", {"pop":-10,"res":-5,"rel":5, "res_regen": 0.1},1]],
            [["You refused the new settlement. ", {"rel":-3},1]]],

        "Moonquake": ["A moonquake has struck the colony, do you take measures to protect your crew? ",
            [["You took measures and minimized damage. ", {"res":-7, "rel": 2},1]],
            [["You ignored the moonquake and suffered damage! ", {"res":-15,},1]]],
       
        "The Cheese Eater": ["The Cheese Eater has arrived. Do you feed it cheese? ",
            [["You fed the Cheese Eater. ", {"res":-5},0.7],["Its still hungry! ",{"res":-15,"pop":-5},0.3]],
            [["YOU MUST FEED THE CHEESE EATER ",{"pop":-5,"res":-10},1]]],
                             
        "Core Expedition": ["A group of your crew propose an expedition to the center of the moon, hoping to find vital resources there. Do you agree? ",
            [["You sent the crew on their way. ", {"res":-5,"pop":-5},1.0,"Core_Expedition_Result"]],
            [["You refuse the expedition. ", {"rel":-5},1]]],

        "Core_Expedition_Result": ["News of the core expedition came back! Do you take the crew back in? ",
            [["The crew caused a moonquake with their equipment, destroying part of the colony! ", {"pop":-15,"res":-10},0.8],["The crew found incredibly rare resources within the core!", {"fund":+25, "res": 15},0.2]],
            [["You refuse to let them in. ", {"rel": -5},1]]],

        "Gambling": ["An alien asks you if you'll invest some funds in a local casino of theirs. Do you accept? ",
            [["You decided to gamble away almost all of your funds.", {"fund":-(fund-10)},0.9],["You won a lot of money! ", {"fund":+(fund)*10},0.1]],
            [["You keep your funds", {"rel":-1},1]]],

        "Hackathon": ["You are asked to join a local alien hackathon known as HackMHS (Moon High School). Do you accept? ",
            [["You join the hackathon and get crushed, just like us in this competition. ", {"u":-1},0.99],["You somehow win the hackathon, just like we will, right judges?😉 ",{"u":99},0.01]],
            [["You do not join the hackathon. ", {"rel":-1},1.0]]],

        "Party (not diddy related)": ["Some of your crew members asks you for permission to host a party. Do you accept? ",
            [["You allow the party and celebrate with the crew. ", {"rel":20,"res":-5},1.0]],
            [["You refuse the party and the crew does not like this! ", {"rel":-10},1]]],

        "Hydroponics": ["Do you want to set up a hydroponic farm? ",
            [["You set up the farm and it generates you 0.25 more resources per turn! ", {"fund": -10, "res": -10, "res_regen": 0.25}, 0.8], ["The farm fails. ", {"fund": -10, "res": -10}, 0.2]],
            [["You don't set up the farm. ", {"rel": -3}, 1]]],                                                                                                          

        "Fundraiser": ["Do you want to host a fundraiser back on Earth?",
            [["The fundraiser was great! You get donations from Earth every turn now! ",{"fund_regen":0.25,"res":-10},0.6],["The fundraiser fails miserably. ",{"fund":-10},0.4]],
            [["You decide not to host the fundraiser. ", {"rel": -3}, 1]]],

        "Recreation cut": ["Do you want to cut recreation time for your crew to get resources? ",
            [["You gained resources, but the crew is not happy. ", {"res": 10, "rel": -15}, 1]],
            [["You don't cut recreation time. ", {"rel": 3}, 1]]]
    }


list_of_dependent_event = ["Core_Expedition_Result","Exploration_Result","Eternal_Result"] # change if more dependent events are added


events_running = events.copy()


for dep_event in list_of_dependent_event:
    if dep_event in events_running:
        events_running.pop(dep_event)


def events_running_initial():
    available_events = events.copy()
    for dep_event in list_of_dependent_event:
        available_events.pop(dep_event, None)
    return available_events

current_event = None
game_turn = 1
game_over = False
game_message = ""
last_result = ""
game_lock = threading.Lock()


def ensure_current_event():
    global current_event, upcoming_events
    if current_event is None and not game_over:
        current_event, upcoming_events = choose_event(upcoming_events)


def state_payload(result=""):
    return {
        "population": pop,
        "resources": res,
        "funding": fund,
        "relations": rel,
        "prompt": current_event[0] if current_event and not game_over else "",
        "round": game_turn,
        "game_over": game_over,
        "message": game_message,
        "result": result,
    }


def get_game_result(turn):
    if turn >= 100:
        return True, "You survived 100 turns and built a rocket to escape! You win."
    if pop <= 0:
        return True, "You have no more people! You lose."
    if pop >= 100:
        return True, "Your population is too big for your colony. You lose."
    if res <= 0:
        return True, "You ran out of resources! You lose."
    if res >= 100:
        return True, "The people have become spoiled with resources and revolted against you! You lose."
    if fund <= 0:
        return True, "Your government stopped giving you funding! You lose."
    if fund >= 100:
        return True, "The government ran out of money to give to you! You lose."
    if rel <= 0:
        return True, "The entire crew mutinied and overthrew you! You lose."
    if rel >= 100:
        return True, "You were unable to sustain your abundance of relationships, and they all hate you! You lose."
    if u <= 0:
        return True, "You died! You lose."
    return False, ""


def main():
    global pop, res, fund, rel, u, run

    turn = 1 # turn count

    # create list of upcoming events (only needs to be done once, will be done once per turn in the choose_event function)
    # Keep a queue of event names so upcoming_events has one consistent type.
   
    upcoming_events = random.sample(list(events_running), min(5, len(events_running)))
    #upcoming_events[:] = random.sample(list(events), min(5, len(events))


    while True:

        dependent_event, upcoming_events, _ = do_turn(all_stats, upcoming_events) # list of all stats updated and dependent event returned so it can be added to events_running
        next_event = upcoming_events[0] if upcoming_events else None

        if dependent_event != "":
            events_running[dependent_event] = events[dependent_event]

        if next_event in list_of_dependent_event:
            events_running.pop(next_event) # remove dependent event from events_running so it doesn't show up in upcoming_events

       
        turn += 1
        print()
        print(f'Rounds survived: {turn-1}')
        print(f'Current population: {pop}, resources: {res}, funding: {fund}, relationships: {rel}, you: {u}')


        if turn >= 100: #win con
            # end game!!
            print("You survived 100 turns and built a rocket to escape! You win!")
            run = False
       
        if pop <= 0 or pop >= 100 or res <= 0 or fund <= 0 or rel <= 0 or u <= 0: # check to end game
            if pop <= 0: # THESE ARE ALL PLACEHOLDERS
                print("You have no more people! You lose.")
            elif pop >= 100:
                print("Your population is too big for your colony. You lose.")
            elif res <= 0:
                print("You ran out of resources! You lose.")
            elif res >= 100:
                print("The people have become spoiled with resources and revolted against you! You lose.")
            elif fund <= 0:
                print("Your government stopped giving you funding! You lose.")
            elif fund >= 100:
                print("The government ran out of money to give to you! You lose.")
            elif rel <= 0:
                print("The entire crew mutinied and overthrew you! You lose.")
            elif rel >= 100:
                print("You were unable to sustain your abundance of relationships, and they all hate you! You lose.")
            elif u <= 0:
                print("You died! You lose.")
            run = False


        if run == False:
            return
       
       

def do_turn(all_stats, upcoming_events, answer=None, event=None):
    global pop, res, fund, rel, u
    dependent_event = ""

    # Stat changes per round
    pop_ch = 0
    res_ch = 0
    fund_ch = 0
    rel_ch = 0
    you_ch = 0
   
    if event is None:
        event, upcoming_events = choose_event(upcoming_events)


    initial_text = event[0]
    yes = event[1]
    no = event[2]
   
    yes_texts = [yes[i][0] for i in range(len(yes))]
    yes_results = [yes[i][1] for i in range(len(yes))]
    yes_probs = [yes[i][2] for i in range(len(yes))]
    no_texts = [no[i][0] for i in range(len(no))]
    no_results = [no[i][1] for i in range(len(no))]
    no_probs = [no[i][2] for i in range(len(no))]
   
    print(initial_text)

   
    if answer is None:
        answer = input("yes or no: ")
    while answer != "yes" and answer != "no":
        answer = input("Invalid resonse! Please enter 'yes' or 'no': ")


    if answer == "yes":
        # pick randomly based on yes_probs
        rand_num = random.random() # random number from 0 to 1
        upper_bounds = [sum(yes_probs[0:i]) for i in range(1, len(yes_probs)+1)]

        if upper_bounds[-1] != 1: # check to make sure probabilities add to 1
            print("Probabilities appear to not add to 1.")
        else:
            # find the first value greater than the random number chosen
            index = 0
            for i in upper_bounds:
                if rand_num <= i:
                    choice = index
                else:
                    index += 1
           
            result = yes_results[choice]
            text = yes_texts[choice]

            # set dependent event
            if len(yes[choice]) > 3:
                dependent_event = str(yes[choice][3])
   
    elif answer == "no":
        # pick randomly based on no_probs
        rand_num = random.random()

        upper_bounds = [sum(no_probs[0:i]) for i in range(1, len(no_probs)+1)]
        if upper_bounds[-1] != 1: # check to make sure probabilities add to 1
            print("Probabilities appear to not add to 1.")
        else:
            # find the first value greater than the random number chosen
            index = 0
            for i in upper_bounds:
                if rand_num <= i:
                    choice = index
                else:
                    index += 1


            result = no_results[choice]
            text = no_texts[choice]

            # set dependent event (if there is one)
            if len(no[choice]) > 3:
                dependent_event = str(no[choice][3])
   
    print(text)
    if "pop" in result:
        pop_ch = result["pop"]
    if "res" in result:
        res_ch = result["res"]
    if "fund" in result:
        fund_ch = result["fund"]
    if "rel" in result:
        rel_ch = result["rel"]  
    if "u" in result:
        you_ch = result["u"]

    # add regen to stat changes
    pop_ch += passive_prfr_regen[0]
    res_ch += passive_prfr_regen[1]
    fund_ch += passive_prfr_regen[2]
    rel_ch += passive_prfr_regen[3]

    # change regen (after above block because regen shouldnt apply the turn it is obtained)
    if "pop_regen" in result: # change
        passive_prfr_regen[0] += result["pop_regen"]
    if "res_regen" in result:
        passive_prfr_regen[1] += result["res_regen"]
    if "fund_regen" in result:
        passive_prfr_regen[2] += result["fund_regen"]
    if "rel_regen" in result:
        passive_prfr_regen[3] += result["rel_regen"]

    # add changes to permanent variables
    pop += pop_ch
    res += res_ch
    fund += fund_ch
    rel += rel_ch
    u += you_ch

    # round stats to prevent rounding errors
    pop = round(pop, 2)
    res = round(res, 2)
    fund = round(fund, 2)
    rel = round(rel, 2)
    u = round(u, 2)


    return dependent_event, upcoming_events, text




def choose_event(upcoming_events):
    global events, events_running, list_of_dependent_event
    
   
    if not upcoming_events: # generate events for the first time
        upcoming_events.extend(random.sample(list(events_running), min(5, len(events_running))))


    event_name = upcoming_events.pop(0)
    available_events = [
        name for name in events_running if name not in upcoming_events and name != event_name
    ] # makes a list of events that could be available to put in upcoming_events


    if available_events:
        upcoming_events.append(random.choice(available_events)) # add new random event at the end of the list

    return events[event_name], upcoming_events




if __name__ == "__main__":
    app.run(debug=False, use_reloader=False)
